"""Turn a model's Markdown grade into per-criterion records, and check it against the case's rubric.

The model is asked for the format the grading seeds use (data/rubrics/README.md):

    **Grade:** 8 / 10

    **Feedback:**
    - C1 Predicate and base case: full (3/3). <one-sentence reason>
    - C2 Induction hypothesis: full (3/3). <reason>
    - C3 Inductive step: partial (2/4). <reason>
    Total: 3 + 3 + 2 = 8.

The criterion-line and Grade patterns follow tools/rubrics.py (CRIT_LINE_RE, GRADE_RE). They are a
little more tolerant of layout (bold, bullet style, capitalised level names), but not of content:
every level, point value, maximum and total is checked.

A failed prediction is never turned into 0 points. A criterion that is missing, written twice, uses
an unknown level, or has points that don't match its level gets level None and score None, and a
status saying why. A valid zero ("none (0/3)") has status "ok" and score 0. A case is valid only
when its status is "ok". The reply is kept verbatim in raw_text.

Case statuses, most serious first:
  request_error       the request failed, so there is no reply
  parse_failure       no reply text, or no grade could be found in it
  invalid_criteria    a criterion is missing, duplicated, unknown, unparseable, or has the wrong points
  inconsistent_total  the criteria are fine, but the Grade or Total line is missing, repeated, or
                      disagrees with them (both lines are part of the documented format)
  ok

The case status describes the output format. Each criterion's status is separate, so a correct
criterion in a case with a bad Grade line is still a correct criterion (see eval/metrics.py).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

LEVELS = ("full", "partial", "minimal", "none")

OK = "ok"
REQUEST_ERROR = "request_error"
PARSE_FAILURE = "parse_failure"
INVALID_CRITERIA = "invalid_criteria"
INCONSISTENT_TOTAL = "inconsistent_total"
CASE_STATUSES = (OK, REQUEST_ERROR, PARSE_FAILURE, INVALID_CRITERIA, INCONSISTENT_TOTAL)

MISSING = "missing"
DUPLICATE = "duplicate"
UNPARSEABLE = "unparseable"
INVALID_LEVEL = "invalid_level"
POINTS_MISMATCH = "points_mismatch"
CRITERION_STATUSES = (OK, MISSING, DUPLICATE, UNPARSEABLE, INVALID_LEVEL, POINTS_MISMATCH)

NUM = r"-?\d+(?:\.\d+)?"
BULLET = r"(?:[-*•]|\d+[.)])"
# "- C1 Predicate and base case: full (3/3). reason", allowing bold around the parts.
HEADER_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<bullet>{BULLET}\s*)?\**\s*(?P<cid>C\d+)(?=[\s:*])(?P<name>[^\n]*?)\s*:\s*\**\s*"
    rf"(?P<level>[A-Za-z]+)\s*\**\s*\(\s*(?P<pts>{NUM})\s*/\s*(?P<max>{NUM})\s*\)\s*\**\s*[.:;,]?\s*(?P<rest>.*)$")
# A bulleted line about a criterion that looks like a grade attempt but doesn't fit HEADER_RE.
CANDIDATE_RE = re.compile(rf"^\s*{BULLET}\s*\**\s*(?P<cid>C\d+)\b")
ATTEMPT_HINT_RE = re.compile(rf"\(\s*{NUM}\s*/\s*{NUM}\s*\)|\b(?:{'|'.join(LEVELS)})\b", re.I)
GRADE_RE = re.compile(rf"\**\s*Grade\s*:\s*\**\s*(?P<got>{NUM})\s*/\s*(?P<out_of>{NUM})", re.I)
TOTAL_RE = re.compile(rf"^\s*\**\s*Total\s*:\s*\**\s*(?P<expr>.*)$", re.I)
THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.S)
EPS = 1e-9


@dataclass
class CriterionResult:
    criterion_id: str
    max: float                      # from the rubric
    status: str
    level: str | None = None        # set only when status is "ok"
    score: float | None = None      # set only when status is "ok"; 0 here is a real zero
    out_of: float | None = None
    justification: str = ""
    claimed: dict | None = None     # what the model wrote, when it was rejected
    problem: str | None = None

    @property
    def valid(self) -> bool:
        return self.status == OK


@dataclass
class ParsedOutput:
    case_status: str
    criteria: list[CriterionResult]
    max_score: float
    raw_text: str | None            # the reply exactly as received
    test_id: str | None = None
    prompt_sha256: str | None = None
    error: str | None = None
    finish_reason: str | None = None
    unknown_criteria: list[dict] = field(default_factory=list)
    stated_grade: float | None = None
    stated_denominator: float | None = None
    total_line_value: float | None = None
    issues: list[str] = field(default_factory=list)     # why the case is not "ok"
    warnings: list[str] = field(default_factory=list)   # format deviations that don't change validity
    thinking_present: bool = False
    truncated: bool = False

    @property
    def valid(self) -> bool:
        return self.case_status == OK

    @property
    def total(self) -> float | None:
        """Sum of the criterion scores, only for a valid case."""
        return sum(c.score for c in self.criteria) if self.valid else None

    def scores(self) -> dict[str, float | None]:
        return {c.criterion_id: c.score for c in self.criteria}

    def to_record(self) -> dict:
        return asdict(self)


def _number(text: str) -> float:
    value = float(text)
    return int(value) if value.is_integer() else value


def _same(a, b) -> bool:
    return abs(float(a) - float(b)) < EPS


def strip_thinking(text: str) -> tuple[str, bool]:
    """Remove thinking text, and say whether there was any.

    Complete <think>...</think> blocks are removed. A lone </think> drops everything before it (some
    chat templates add the opening tag themselves), and an unclosed <think> drops everything after it.
    """
    if "<think>" not in text and "</think>" not in text:
        return text, False
    text = THINK_BLOCK_RE.sub("", text)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    if "<think>" in text:
        text = text.split("<think>", 1)[0]
    return text, True


def _header(line: str):
    """The header match for a line, if it is one. A header needs a bullet or must start the
    line: an indented "C1 is: full (3/3) ..." inside a reason is not one."""
    m = HEADER_RE.match(line)
    return m if m and (m.group("bullet") or not m.group("indent")) else None


def _read_lines(text: str):
    """Find criterion headers (with their continuation lines), stray criterion lines,
    Grade lines and Total lines."""
    lines = text.splitlines()
    headers, strays, grades, totals = [], [], [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        for m in GRADE_RE.finditer(line):
            grades.append((_number(m.group("got")), _number(m.group("out_of"))))
        tm = TOTAL_RE.match(line)
        if tm:
            totals.append(tm.group("expr"))
            i += 1
            continue
        hm = _header(line)
        if hm:
            parts = [hm.group("rest")]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if (not nxt.strip() or CANDIDATE_RE.match(nxt) or _header(nxt)
                        or TOTAL_RE.match(nxt) or GRADE_RE.search(nxt) or nxt.lstrip().startswith(("**", "#"))):
                    break
                parts.append(nxt)
                j += 1
            headers.append({"cid": hm.group("cid"), "name": hm.group("name").strip(" *"),
                            "level": hm.group("level"), "pts": hm.group("pts"), "max": hm.group("max"),
                            "justification": re.sub(r"\s+", " ", " ".join(parts)).strip(),
                            "line": line})
            i = j
            continue
        cm = CANDIDATE_RE.match(line)
        if cm and ATTEMPT_HINT_RE.search(line):
            strays.append({"cid": cm.group("cid"), "line": line})
        i += 1
    return headers, strays, grades, totals


def _check_criterion(spec: dict, found: list[dict], strays: list[dict]) -> CriterionResult:
    cid, cmax = spec["id"], spec["max"]
    points = {name: spec["levels"][name]["points"] for name in LEVELS}
    if not found:
        mine = [s["line"] for s in strays if s["cid"] == cid]
        if mine:
            return CriterionResult(cid, cmax, UNPARSEABLE, claimed={"lines": mine},
                                   problem=f"{cid} line does not have the form 'level (points/max)'")
        return CriterionResult(cid, cmax, MISSING, problem=f"no line grades {cid}")
    if len(found) > 1:
        return CriterionResult(cid, cmax, DUPLICATE, claimed={"lines": [f["line"] for f in found]},
                               problem=f"{cid} is graded {len(found)} times")
    f = found[0]
    level = f["level"].lower()
    claimed = {"level": f["level"], "points": _number(f["pts"]), "out_of": _number(f["max"])}
    if level not in LEVELS:
        return CriterionResult(cid, cmax, INVALID_LEVEL, claimed=claimed, justification=f["justification"],
                               problem=f"{cid} level {f['level']!r} is not one of {', '.join(LEVELS)}")
    if not _same(f["max"], cmax):
        return CriterionResult(cid, cmax, POINTS_MISMATCH, claimed=claimed, justification=f["justification"],
                               problem=f"{cid} is marked out of {f['max']} but its maximum is {cmax}")
    if not _same(f["pts"], points[level]):
        return CriterionResult(cid, cmax, POINTS_MISMATCH, claimed=claimed, justification=f["justification"],
                               problem=f"{cid} {level} is worth {points[level]} points, not {f['pts']}")
    return CriterionResult(cid, cmax, OK, level=level, score=points[level], out_of=cmax,
                           justification=f["justification"])


def _total_value(expr: str) -> tuple[float | None, str | None]:
    """The value a Total line states, and a problem if its own arithmetic is wrong."""
    nums = re.findall(NUM, expr)
    if not nums:
        return None, "the Total line has no number"
    value = _number(nums[-1])
    if "=" in expr:
        left = expr.rsplit("=", 1)[0]
        terms = re.findall(NUM, left)
        if terms and "+" in left and not _same(sum(float(t) for t in terms), value):
            return value, f"the Total line's sum {left.strip()} is not {value}"
    return value, None


def parse_text(text: str | None, rubric: list[dict], *, error: str | None = None,
               finish_reason: str | None = None, test_id: str | None = None,
               prompt_sha256: str | None = None) -> ParsedOutput:
    """Parse one reply against the case's rubric (the test case's `rubric` list)."""
    max_score = _number(str(sum(float(c["max"]) for c in rubric)))
    out = ParsedOutput(case_status=OK, criteria=[], max_score=max_score, raw_text=text, test_id=test_id,
                       prompt_sha256=prompt_sha256, error=error, finish_reason=finish_reason,
                       truncated=finish_reason == "length")

    def fail(status, issue, criterion_status=MISSING):
        out.case_status = status
        out.issues.append(issue)
        out.criteria = [CriterionResult(c["id"], c["max"], criterion_status, problem=issue) for c in rubric]
        return out

    if error is not None:
        return fail(REQUEST_ERROR, f"request failed: {error}")
    if text is None or not text.strip():
        return fail(PARSE_FAILURE, "the reply is empty")

    body, out.thinking_present = strip_thinking(text)
    if out.thinking_present:
        out.warnings.append("the reply contains thinking text")
    if out.truncated:
        out.warnings.append("the reply was cut off at max_tokens")

    headers, strays, grades, totals = _read_lines(body)
    if not headers and not strays and not grades:
        return fail(PARSE_FAILURE, "no grade found in the reply")

    # The stated totals are recorded even when the criteria are invalid, for diagnosis.
    if grades:
        out.stated_grade, out.stated_denominator = grades[0]
    total_value, total_problem = _total_value(totals[0]) if len(totals) == 1 else (None, None)
    out.total_line_value = total_value

    rubric_ids = [c["id"] for c in rubric]
    for h in headers:
        if h["cid"] not in rubric_ids:
            out.unknown_criteria.append({"criterion_id": h["cid"], "line": h["line"]})
    out.criteria = [_check_criterion(spec, [h for h in headers if h["cid"] == spec["id"]], strays)
                    for spec in rubric]
    graded = [h["cid"] for h in headers if h["cid"] in rubric_ids]
    if graded and len(set(graded)) == len(graded) and graded != [c for c in rubric_ids if c in graded]:
        out.warnings.append("criteria are not in rubric order")
    for c in out.criteria:
        if c.valid and not c.justification:
            out.warnings.append(f"{c.criterion_id} has no reason")

    bad = [c for c in out.criteria if not c.valid]
    if bad or out.unknown_criteria:
        out.case_status = INVALID_CRITERIA
        out.issues += [c.problem for c in bad]
        out.issues += [f"{u['criterion_id']} is not a criterion in this rubric" for u in out.unknown_criteria]
        return out

    total = sum(c.score for c in out.criteria)
    if not grades:
        out.issues.append("no '**Grade:** x / N' line")
    elif len(set(grades)) > 1:
        out.issues.append(f"the Grade is stated more than once with different values: {sorted(set(grades))}")
    else:
        if not _same(out.stated_denominator, max_score):
            out.issues.append(f"the Grade is out of {out.stated_denominator}, but the rubric totals {max_score}")
        if not _same(out.stated_grade, total):
            out.issues.append(f"the Grade is {out.stated_grade}, but the criteria add up to {total}")
    if not totals:
        out.issues.append("no 'Total:' line")
    elif len(totals) > 1:
        out.issues.append("more than one Total line")
    elif total_problem:
        out.issues.append(total_problem)
    elif not _same(total_value, total):
        out.issues.append(f"the Total line says {total_value}, but the criteria add up to {total}")
    if out.issues:
        out.case_status = INCONSISTENT_TOTAL
    return out


def parse_generation(generation, case: dict) -> ParsedOutput:
    """Parse a backends.Generation against its test case."""
    return parse_text(generation.text, case["rubric"], error=generation.error,
                      finish_reason=generation.finish_reason, test_id=generation.test_id,
                      prompt_sha256=generation.prompt_sha256)
