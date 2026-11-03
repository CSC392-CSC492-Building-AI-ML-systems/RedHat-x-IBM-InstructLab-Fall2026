#!/usr/bin/env python3
"""Filter a generated training file before it goes into training.

Reads one or more `skills_train_msgs*.jsonl` files (ilab's output, or combine_sdg.py's) and
writes a cleaned copy, the dropped rows with their reasons, and a short report.

Grading rows (taxonomy paths containing "grading") are dropped when:
  no_student_answer     the prompt has no student answer after "Student Answer:"
  unknown_rubric        the question and rubric in the prompt are not exactly one of the files
                        in data/rubrics/
                        (skip this check with --allow-unknown-rubric)
  bad_rubric            the rubric's levels or points don't add up
  no_grade              there is no "**Grade:** x / y" line
  grade_total           the grade is out of the wrong total, or outside 0..total
  criterion_missing     a rubric criterion has no "- Cn ...: level (x/max)" line
  criterion_repeated    a criterion is graded more than once (usually a self-correction)
  unknown_criterion     a graded criterion is not in the rubric
  wrong_level_points    a level is given points the rubric doesn't give it
  sum_not_grade         the criterion points don't add up to the grade
  total_line            the "Total: a + b = x" line is missing, wrong, or not last
  self_correction       the answer revises itself ("Wait", "Revised feedback", ...)
  template_token        the prompt or answer contains a <|...|> chat-template token
  answer_is_prompt      the "student answer" is a copy of the question or rubric
  duplicate_answer      the same student answer to the same question was already kept
  regex_grade_wrong     (regex rubrics only) C1 or C2 disagrees with a brute-force test of the
                        student's regular expression on every string up to length 8

Knowledge rows: <|...|> tokens are removed from prompts; rows are dropped when the answer
contains such a token, has fewer than 8 words, or stops mid-sentence (keep those with
--keep-unfinished). Other rows (LaTeX, proof structure, spellcheck) are kept unchanged.

Usage (from the repository root):
  python3 tools/filter_skills.py OUT/run/skills_train_msgs_*.jsonl --out data/review/pilot_regex

Writes OUT_DIR/train_filtered.jsonl, OUT_DIR/dropped.jsonl and OUT_DIR/report.md.
Requires: pip install ruamel.yaml (for reading the rubric files).
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rubrics as R  # noqa: E402  (tools/rubrics.py)

EPS = 1e-9
TOKEN_RE = re.compile(r"<\|[^|<>\s]{1,30}\|>")
SELF_CORRECTION_RE = re.compile(
    r"\b(wait\b|revised (feedback|grade)|correction:|on second thought|let me re|re-evaluat|"
    r"i made an error|actually,)", re.I)
TOTAL_LINE_RE = re.compile(r"^\s*Total:\s*([0-9.+\s]+?)=\s*([\d.]+)\.?\s*$", re.M)
LINE_RE = re.compile(
    r"^\s*-\s*(C\d+)\b[^\n]*?:\s*\**(full|partial|minimal|none)\**\s*\((\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\)",
    re.M | re.I)
FINISHED_RE = re.compile(r"[.!?)\]$`*\"'|]\s*$")
# Languages for the regex rubrics, so C1 (soundness) and C2 (completeness) can be checked by
# testing the student's expression. Add an entry when you add a regex rubric file.
REGEX_LANGUAGES = {
    "regex_no_double_zero": ("01", lambda w: "00" not in w),
    "regex_even_zeros": ("01", lambda w: w.count("0") % 2 == 0),
    "regex_ends_01": ("01", lambda w: w.endswith("01")),
    "regex_exactly_one_b": ("ab", lambda w: w.count("b") == 1),
    "regex_length_multiple_3": ("01", lambda w: len(w) % 3 == 0),
    "regex_same_first_last": ("ab", lambda w: len(w) > 0 and w[0] == w[-1]),
}
REGEX_MAX_LEN = 8
KNOWLEDGE = ("document_knowledge_qa", "document_knowledge_qa_raft_p0.4")


def metadata(row) -> dict:
    md = row.get("metadata") or {}
    if isinstance(md, str):
        try:
            md = json.loads(md)
        except json.JSONDecodeError:
            md = {}
    return md


def last(messages, role):
    for m in reversed(messages):
        if m.get("role") == role:
            return m
    return None


def regex_facts(student: str, rubric_id: str):
    """Return (sound, complete) for the student's 'r = ...' expression, or None if it can't be read."""
    if rubric_id not in REGEX_LANGUAGES:
        return None
    m = re.search(r"\br\s*=\s*([^\n]+)", student)
    if not m:
        return None
    expr = m.group(1).strip().rstrip(".")
    if not re.fullmatch(r"[01abε()+*\s]+", expr):
        return None  # prose, "...", or symbols we don't translate
    pattern = expr.replace(" ", "").replace("ε", "").replace("+", "|")
    try:
        compiled = re.compile("(?:" + pattern + ")\\Z")
    except re.error:
        return None
    alphabet, in_lang = REGEX_LANGUAGES[rubric_id]
    words = ("".join(t) for n in range(REGEX_MAX_LEN + 1) for t in itertools.product(alphabet, repeat=n))
    sound = complete = True
    for w in words:
        hit = compiled.match(w) is not None
        if hit and not in_lang(w):
            sound = False
        if not hit and in_lang(w):
            complete = False
    return sound, complete


def check_grading(prompt: str, answer: str, known_blocks: dict, allow_unknown: bool):
    """Return (reasons, info) for one grading row."""
    reasons, info = [], {}
    head, _, student = prompt.partition("Student Answer:")
    if len(student.split()) < 2:
        reasons.append("no_student_answer")
    elif "Rubric (Total" in student or "Grade the student answer" in student:
        reasons.append("answer_is_prompt")
    info["student"] = R.norm(student)

    block_start = re.search(r"^\s*Rubric\b", head, re.M)
    block = head[block_start.start():] if block_start else ""
    info["question"] = R.norm(head.split("Question:", 1)[-1].split("Rubric", 1)[0])[:160]

    flat = R.norm(prompt)
    info["rubric_id"] = next((rid for rid, b in known_blocks.items() if b in flat), None)
    if info["rubric_id"] is None and not allow_unknown:
        reasons.append("unknown_rubric")

    total_m = R.TOTAL_RE.search(block)
    crits = R.parse_criteria(block)
    total = float(total_m.group(1)) if total_m else None
    if total is None or not crits:
        reasons.append("bad_rubric")
    else:
        if abs(sum(c["max"] for c in crits.values()) - total) > EPS:
            reasons.append("bad_rubric")
        for c in crits.values():
            pts = [c["levels"].get(k) for k in R.LEVELS]
            if None in pts or abs(pts[0] - c["max"]) > EPS or pts[-1] != 0 or any(a <= b for a, b in zip(pts, pts[1:])):
                reasons.append("bad_rubric")
                break

    if "<|" in prompt or "<|" in answer:
        reasons.append("template_token")
    if SELF_CORRECTION_RE.search(answer):
        reasons.append("self_correction")

    grade_m = R.GRADE_RE.search(answer)
    if not grade_m:
        reasons.append("no_grade")
        return sorted(set(reasons)), info
    got, out_of = float(grade_m.group(1)), float(grade_m.group(2))
    info["grade"], info["total"] = got, total
    if total is not None and (abs(out_of - total) > EPS or got < -EPS or got > total + EPS):
        reasons.append("grade_total")

    found = LINE_RE.findall(answer)
    counts = Counter(cid for cid, *_ in found)
    if any(counts[cid] == 0 for cid in crits):
        reasons.append("criterion_missing")
    if any(n > 1 for n in counts.values()):
        reasons.append("criterion_repeated")
    point_sum = 0.0
    for cid, level, pts, mx in found:
        pts, mx = float(pts), float(mx)
        point_sum += pts
        if cid not in crits:
            reasons.append("unknown_criterion")
            continue
        want = crits[cid]["levels"].get(level.lower())
        if abs(mx - crits[cid]["max"]) > EPS or (want is not None and abs(want - pts) > EPS):
            reasons.append("wrong_level_points")
    if found and abs(point_sum - got) > EPS:
        reasons.append("sum_not_grade")

    lines = [ln for ln in answer.strip().splitlines() if ln.strip()]
    tm = TOTAL_LINE_RE.search(answer)
    if not tm or not lines or not lines[-1].lstrip().startswith("Total:"):
        reasons.append("total_line")
    else:
        parts = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", tm.group(1))]
        if abs(sum(parts) - float(tm.group(2))) > EPS or abs(float(tm.group(2)) - got) > EPS:
            reasons.append("total_line")

    facts = regex_facts(student, info.get("rubric_id") or "")
    if facts is not None:
        levels = {cid: level.lower() for cid, level, *_ in found}
        sound, complete = facts
        if (levels.get("C1") == "full") != sound or (levels.get("C2") == "full") != complete:
            reasons.append("regex_grade_wrong")
    return sorted(set(reasons)), info


def check_knowledge(row, keep_unfinished: bool):
    msgs = row["messages"]
    user, asst = last(msgs, "user"), last(msgs, "assistant")
    reasons = []
    if user is not None and "<|" in user["content"]:
        user["content"] = TOKEN_RE.sub("", user["content"])
    answer = asst["content"] if asst else ""
    if "<|" in answer:
        reasons.append("template_token")
    if len(answer.split()) < 8:
        reasons.append("short_answer")
    if not keep_unfinished and not FINISHED_RE.search(answer.strip()):
        reasons.append("unfinished_answer")
    return reasons


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="generated .jsonl files")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--rubric-dir", default="data/rubrics", help="rubric files (default: data/rubrics)")
    ap.add_argument("--allow-unknown-rubric", action="store_true",
                    help="keep grading rows whose rubric is not in --rubric-dir")
    ap.add_argument("--keep-unfinished", action="store_true",
                    help="keep knowledge answers that stop mid-sentence")
    args = ap.parse_args()

    # Match the whole question-and-rubric context when the rubric file has a question, so an edited
    # question also counts as "not our rubric".
    known = {r["id"]: R.norm(r.get("context") or r["block"]) for r in R.load_rubrics(Path(args.rubric_dir))}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    kept_n = Counter()
    dropped_n = Counter()
    reason_n = defaultdict(Counter)
    seen_answers = set()
    folders = defaultdict(lambda: {"rows": 0, "kept": 0, "known": 0, "full": 0, "questions": set(),
                                   "kept_questions": set(), "judge": Counter(), "reasons": Counter()})

    with open(out / "train_filtered.jsonl", "w", encoding="utf-8") as keep_f, \
            open(out / "dropped.jsonl", "w", encoding="utf-8") as drop_f:
        for path in args.inputs:
            with open(path, encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    md = metadata(row)
                    leaf = md.get("leaf_node_path", "")
                    msgs = row.get("messages", [])
                    if "_grading_" in leaf:
                        kind = "grading"
                        folder = leaf.split("_csc236_")[-1]
                        user, asst = last(msgs, "user"), last(msgs, "assistant")
                        reasons, info = check_grading(user["content"] if user else "",
                                                      asst["content"] if asst else "", known,
                                                      args.allow_unknown_rubric)
                        key = (info.get("rubric_id") or info.get("question"), info.get("student"))
                        if not reasons and key in seen_answers:
                            reasons.append("duplicate_answer")
                        if not reasons:
                            seen_answers.add(key)
                        f = folders[folder]
                        f["rows"] += 1
                        f["known"] += info.get("rubric_id") is not None
                        f["questions"].add(info.get("question"))
                        f["judge"][md.get("score")] += 1
                        f["reasons"].update(reasons)
                        if not reasons:
                            f["kept"] += 1
                            f["kept_questions"].add(info.get("question"))
                            total = info.get("total") or 0
                            f["full"] += bool(total) and abs(info["grade"] - total) < EPS
                    elif md.get("dataset") in KNOWLEDGE:
                        kind = "knowledge"
                        reasons = check_knowledge(row, args.keep_unfinished)
                    else:
                        kind = "other_skill" if leaf else "other"
                        reasons = []
                    if reasons:
                        dropped_n[kind] += 1
                        reason_n[kind].update(reasons)
                        drop_f.write(json.dumps({"file": path, "line": line_no, "kind": kind,
                                                 "folder": leaf, "reasons": reasons, "id": row.get("id")},
                                                ensure_ascii=False) + "\n")
                    else:
                        kept_n[kind] += 1
                        keep_f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---- report
    lines = ["# Filter report", "", f"Inputs: {', '.join(args.inputs)}", "",
             "| Rows | Kept | Dropped |", "| --- | --- | --- |"]
    for kind in ("grading", "other_skill", "knowledge", "other"):
        if kept_n[kind] or dropped_n[kind]:
            lines.append(f"| {kind} | {kept_n[kind]} | {dropped_n[kind]} |")
    for kind, counter in reason_n.items():
        lines += ["", f"## Drop reasons: {kind}", "", "| Reason | Rows |", "| --- | --- |"]
        lines += [f"| {r} | {n} |" for r, n in counter.most_common()]
    if folders:
        lines += ["", "## Grading folders", "",
                  "| Folder | Rows | Uses our rubric | Kept | Kept with full marks | Distinct questions (kept) | Judge scores |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for name, f in sorted(folders.items()):
            share = f"{f['full'] / f['kept']:.0%}" if f["kept"] else "-"
            judge = ", ".join(f"{k}: {v}" for k, v in sorted(f["judge"].items(), key=lambda kv: str(kv[0])))
            lines.append(f"| {name} | {f['rows']} | {f['known']} of {f['rows']} | {f['kept']} | {share} | "
                         f"{len(f['kept_questions'])} | {judge} |")
        rows = sum(f["rows"] for f in folders.values())
        known_n = sum(f["known"] for f in folders.values())
        kept = sum(f["kept"] for f in folders.values())
        full = sum(f["full"] for f in folders.values())
        lines += ["", "## Pilot go criteria", "",
                  "| Check | Target | Result | Pass |", "| --- | --- | --- | --- |",
                  f"| Rows that use one of our rubrics | 100% | {known_n} of {rows} | {'yes' if rows and known_n == rows else 'no'} |",
                  f"| Kept rows with full marks | 30% or less | {full} of {kept} | {'yes' if kept and full / kept <= 0.30 else 'no'} |",
                  f"| Rows kept | 30 or more per pilot folder | {kept} | {'yes' if kept >= 30 * max(1, len(folders)) else 'no'} |",
                  "", "Also read about 10 kept rows by hand: the script cannot tell a lenient grade from a fair one."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {out / 'train_filtered.jsonl'}, {out / 'dropped.jsonl'} and {out / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
