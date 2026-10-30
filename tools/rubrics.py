#!/usr/bin/env python3
"""Keep grading rubrics in one place and check the grading seed files.

InstructLab only reads qna.yaml, so every grading seed carries its question and rubric inside its
own `context`. This script builds those contexts from one source file per question in
data/rubrics/, so all copies stay identical, and checks the seeds before data generation.

Rubric files use the same shape as the test set: criteria C1..Cn, each with a max and four levels
(full, partial, minimal, none). See data/rubrics/README.md.

Commands
  stamp     Rebuild every matching seed context from data/rubrics/ (shows the diff; add --write)
  validate  Check every qna.yaml under the taxonomy, and every rubric file
  extract   Copy the rubric block out of an older qna.yaml into a block-only rubric file

Examples (from the repository root)
  python tools/rubrics.py stamp
  python tools/rubrics.py stamp --write
  python tools/rubrics.py validate

Requires: pip install ruamel.yaml
"""

from __future__ import annotations

import argparse
import difflib
import glob
import json
import re
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path

try:
    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import LiteralScalarString
except ImportError:  # pragma: no cover
    sys.exit("This script needs ruamel.yaml: pip install ruamel.yaml")


RUBRIC_DIR_DEFAULT = "data/rubrics"
TAXONOMY_DEFAULT = "taxonomy"
LEVELS = ["full", "partial", "minimal", "none"]
WRAP = 94

INSTRUCTION = ("Grade the student answer against the question and rubric below. For each criterion,\n"
               "choose the level that fits the answer and give a one-sentence reason.")

RUBRIC_START = re.compile(r"^\s*Rubric\b")
TOTAL_RE = re.compile(r"Rubric\s*\(Total\s+([\d.]+)\s*pts?\)", re.I)
ITEM_RE = re.compile(r"^\s*-\s*(.+?):\s*([\d.]+)\s*pts?\b", re.I)
CRIT_DEF_RE = re.compile(r"^-\s*(C\d+)\b.*:\s*([\d.]+)\s*pts?\.?\s*$")
LEVEL_DEF_RE = re.compile(r"^\s+(full|partial|minimal|none)\s*\(([\d.]+)\):")
CRIT_LINE_RE = re.compile(
    r"^\s*-\s*(C\d+)\b[^\n]*?:\s*(full|partial|minimal|none)\s*\((\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\)",
    re.M)
GRADE_RE = re.compile(r"\*\*Grade:\*\*\s*([\d.]+)\s*/\s*([\d.]+)")
POINTS_RE = re.compile(r"\((-?\d+(?:\.\d+)?)(?:\s*/\s*\d+(?:\.\d+)?)?\)")
QUESTION_LINE_RE = re.compile(r"^\s*Question:\s*(.+)$", re.M)
ANSWER_LABELS = ("Student Answer:", "Student Submission:")

GENERIC_FEEDBACK = [
    "perfect execution",
    "flawless",
    "standard processing applied",
    "initial logic and parameters are validated",
    "excellent work",
    "great job",
]
HEDGES = ["maybe", "might be", "seems", "probably", "arguably", "sort of"]
PLACEHOLDER_AUTHORS = {"", "your_username", "username", "todo"}
EPS = 1e-9


# --------------------------------------------------------------------------- helpers

def make_yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return make_yaml().load(fh)


def dump(data, path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        make_yaml().dump(data, fh)


def split_context(context: str) -> tuple[str, str]:
    """Split a context into (text before the rubric, rubric block to the end)."""
    lines = context.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if RUBRIC_START.match(line):
            return "".join(lines[:i]), "".join(lines[i:])
    return context, ""


def norm(text) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def fmt(n: float) -> str:
    return f"{float(n):g}"


def wrap(text: str, first: str, rest: str) -> list[str]:
    return textwrap.wrap(norm(text), width=WRAP, initial_indent=first, subsequent_indent=rest,
                         break_on_hyphens=False, break_long_words=False)


def qa_pairs(seed):
    """Yield (index, question, answer) for v2 (flat) and v3 (questions_and_answers) seeds."""
    if "questions_and_answers" in seed:
        for j, qa in enumerate(seed["questions_and_answers"] or [], 1):
            yield j, str(qa.get("question", "")), str(qa.get("answer", ""))
    elif "question" in seed:
        yield 1, str(seed.get("question", "")), str(seed.get("answer", ""))


def rubric_items(block: str) -> tuple[float | None, list[tuple[str, float]]]:
    m = TOTAL_RE.search(block)
    total = float(m.group(1)) if m else None
    items = []
    for line in block.splitlines():
        im = ITEM_RE.match(line)
        if im:
            items.append((im.group(1).strip(), float(im.group(2))))
    return total, items


def parse_criteria(block: str) -> dict[str, dict]:
    """Read C1..Cn and their level points back out of a rendered rubric block."""
    crits, current = {}, None
    for line in block.splitlines():
        cm = CRIT_DEF_RE.match(line)
        if cm:
            current = cm.group(1)
            crits[current] = {"max": float(cm.group(2)), "levels": {}}
            continue
        lm = LEVEL_DEF_RE.match(line)
        if lm and current:
            crits[current]["levels"][lm.group(1)] = float(lm.group(2))
    return crits


# --------------------------------------------------------------------------- rubric files

def render_block(r: dict) -> str:
    total = sum(float(c["max"]) for c in r["criteria"])
    lines = [f"Rubric (Total {fmt(total)} pts):"]
    for c in r["criteria"]:
        lines.append(f"- {c['id']} {norm(c['criterion'])}: {fmt(c['max'])} pts.")
        for level in LEVELS:
            spec = c["levels"][level]
            lines += wrap(f"{level} ({fmt(spec['points'])}): {spec['expectation']}", "  ", "    ")
    rules = r.get("general_rules") or []
    if rules:
        lines.append("General rules:")
        for n, rule in enumerate(rules, 1):
            lines += wrap(f"{n}. {rule}", "", "   ")
    return "\n".join(lines) + "\n"


def render_context(r: dict) -> str:
    question = "\n".join(line.rstrip() for line in str(r["question"]).strip("\n").splitlines())
    return f"{INSTRUCTION}\n\nQuestion:\n{question}\n\n{render_block(r)}"


def check_rubric_file(r: dict) -> list[str]:
    problems = []
    seen = set()
    for c in r.get("criteria", []):
        cid = c.get("id")
        if cid in seen:
            problems.append(f"{cid} appears twice")
        seen.add(cid)
        levels = c.get("levels") or {}
        if list(levels) != LEVELS:
            problems.append(f"{cid} levels are {list(levels)}; expected {LEVELS} in that order")
            continue
        pts = [float(levels[name]["points"]) for name in LEVELS]
        if abs(pts[0] - float(c["max"])) > EPS:
            problems.append(f"{cid} full is {fmt(pts[0])} points but max is {fmt(c['max'])}")
        if abs(pts[-1]) > EPS:
            problems.append(f"{cid} none should be 0 points")
        if any(a <= b for a, b in zip(pts, pts[1:])):
            problems.append(f"{cid} level points must strictly decrease: {pts}")
        for name in LEVELS:
            if not norm(levels[name].get("expectation", "")):
                problems.append(f"{cid} {name} has no expectation")
    return problems


def load_rubrics(rubric_dir: Path) -> list[dict]:
    rubrics = []
    if not rubric_dir.exists():
        return rubrics
    for path in sorted(rubric_dir.glob("*.y*ml")):
        data = load(path)
        if not data:
            continue
        data["_path"] = path
        if "criteria" in data:
            data["block"] = render_block(data)
            if "question" in data:
                data["context"] = render_context(data)
        elif "block" in data:
            data["block"] = str(data["block"]).rstrip("\n") + "\n"
        else:
            print(f"{path}: skipped (no 'criteria' or 'block')")
            continue
        rubrics.append(data)
    return rubrics


def target_files(rubric: dict, root: Path) -> list[Path]:
    found = set()
    for pattern in rubric.get("targets", []):
        for p in glob.glob(str(root / pattern), recursive=True):
            found.add(Path(p).resolve())
    return sorted(found)


def expected_context(rubric: dict, context: str) -> str:
    if "context" in rubric:
        return rubric["context"]
    head, old_block = split_context(context)
    if not old_block:
        head = head.rstrip("\n") + "\n"
    return head + rubric["block"]


# --------------------------------------------------------------------------- extract

def cmd_extract(args) -> int:
    path = Path(args.qna)
    data = load(path)
    for seed in data.get("seed_examples", []):
        context = str(seed.get("context", ""))
        if args.match and args.match not in context:
            continue
        _, block = split_context(context)
        if not block:
            continue
        match = args.match
        if not match:
            qm = QUESTION_LINE_RE.search(context)
            match = qm.group(1).strip() if qm else ""
        target = args.target or f"**/{path.parent.name}/qna.yaml"
        out = Path(args.rubric_dir) / f"{args.id}.yaml"
        if out.exists() and not args.force:
            print(f"{out} already exists (use --force to overwrite)")
            return 1
        out.parent.mkdir(parents=True, exist_ok=True)
        body = "".join(f"  {line}" if line.strip() else "\n"
                       for line in block.rstrip("\n").splitlines(keepends=True))
        out.write_text(
            f"# Block-only rubric for {args.id}, extracted from {path}.\n"
            "# Consider rewriting it with criteria and levels (see README.md).\n"
            f"id: {args.id}\n"
            "targets:\n"
            f"  - {json.dumps(target)}\n"
            f"match: {json.dumps(match)}\n"
            "block: |\n"
            f"{body}\n",
            encoding="utf-8",
        )
        print(f"Wrote {out}")
        return 0
    print(f"No context with a 'Rubric' block in {path}")
    return 1


# --------------------------------------------------------------------------- stamp

def cmd_stamp(args) -> int:
    root = Path(args.taxonomy)
    rubrics = load_rubrics(Path(args.rubric_dir))
    pending = 0
    for rubric in rubrics:
        files = target_files(rubric, root)
        if not files:
            print(f"[warn] {rubric['_path'].name}: no qna.yaml matches its targets")
            continue
        for path in files:
            data = load(path)
            changed, hits = False, 0
            for i, seed in enumerate(data.get("seed_examples", []), 1):
                context = seed.get("context")
                if context is None or rubric.get("match", "") not in str(context):
                    continue
                hits += 1
                new_context = expected_context(rubric, str(context))
                if new_context != str(context):
                    changed = True
                    pending += 1
                    if not args.quiet:
                        print(f"--- {path} seed {i}")
                        sys.stdout.writelines(difflib.unified_diff(
                            str(context).splitlines(keepends=True),
                            new_context.splitlines(keepends=True),
                            "current", rubric["_path"].name, n=0))
                    seed["context"] = LiteralScalarString(new_context)
            if hits == 0:
                print(f"[warn] {path}: no seed context contains the match text from {rubric['_path'].name}")
            if changed and args.write:
                dump(data, path)
                print(f"Updated {path}")
    if pending and not args.write:
        print(f"\n{pending} context(s) out of date. Run with --write to update them.")
        return 1
    if not pending:
        print("All contexts are up to date.")
    return 0


# --------------------------------------------------------------------------- validate

class Report:
    def __init__(self):
        self.errors = 0
        self.warnings = 0

    def error(self, path, where, msg):
        self.errors += 1
        print(f"{path}: [ERROR] {where}{msg}")

    def warn(self, path, where, msg):
        self.warnings += 1
        print(f"{path}: [warn]  {where}{msg}")


def check_criterion_lines(path, where, fb, crits, got, rep) -> None:
    found = CRIT_LINE_RE.findall(fb)
    counts = Counter(cid for cid, *_ in found)
    for cid in crits:
        if counts[cid] == 0:
            rep.error(path, where, f"no feedback line for {cid} (expected '- {cid} ...: level (x/max)')")
        elif counts[cid] > 1:
            rep.error(path, where, f"{cid} is graded more than once")
    total = 0.0
    for cid, level, pts, out_of in found:
        if cid not in crits:
            rep.error(path, where, f"{cid} is not a criterion in this rubric")
            continue
        spec = crits[cid]
        pts, out_of = float(pts), float(out_of)
        total += pts
        if abs(out_of - spec["max"]) > EPS:
            rep.error(path, where, f"{cid} is marked out of {fmt(out_of)} but its max is {fmt(spec['max'])}")
        want = spec["levels"].get(level)
        if want is not None and abs(want - pts) > EPS:
            rep.error(path, where, f"{cid} level '{level}' is worth {fmt(want)}, not {fmt(pts)}")
    if found and abs(total - got) > EPS:
        rep.error(path, where, f"criterion points sum to {fmt(total)} but the grade is {fmt(got)}")


def validate_file(path: Path, rubrics: list[dict], root: Path, rep: Report) -> None:
    raw = path.read_text(encoding="utf-8")
    try:
        data = load(path)
    except Exception as exc:  # noqa: BLE001
        rep.error(path, "", f"YAML does not parse: {exc}")
        return
    if not isinstance(data, dict):
        rep.error(path, "", "file is empty or not a mapping")
        return

    trailing = [n for n, line in enumerate(raw.splitlines(), 1) if line != line.rstrip()]
    long_lines = [n for n, line in enumerate(raw.splitlines(), 1) if len(line) > 120]
    if trailing:
        rep.error(path, "", f"trailing whitespace on line(s) {', '.join(map(str, trailing))} (ilab's linter rejects it)")
    if long_lines:
        rep.warn(path, "", f"{len(long_lines)} line(s) over 120 characters, which the taxonomy linter "
                          f"usually rejects: {', '.join(map(str, long_lines))}")
    if "<|" in raw:
        rep.error(path, "", "contains a <|...|> chat-template token")
    if str(data.get("created_by", "")).strip().lower() in PLACEHOLDER_AUTHORS:
        rep.error(path, "", f"created_by is a placeholder ({data.get('created_by')!r})")
    if not (path.parent / "attribution.txt").exists():
        rep.warn(path, "", "no attribution.txt next to this qna.yaml")

    seeds = data.get("seed_examples") or []
    if len(seeds) < 5:
        rep.warn(path, "", f"only {len(seeds)} seed_examples (InstructLab expects at least 5)")

    questions, answers = Counter(), Counter()
    grades = []  # as a fraction of each rubric's total
    rubric_by_question = defaultdict(set)
    resolved = path.resolve()

    for i, seed in enumerate(seeds, 1):
        context = str(seed.get("context", "") or "")
        _, block = split_context(context)
        grading = bool(TOTAL_RE.search(block))
        total = None
        crits = {}

        if grading:
            total, items = rubric_items(block)
            item_sum = sum(p for _, p in items)
            if abs(item_sum - total) > EPS:
                rep.error(path, f"seed {i}: ",
                          f"rubric items sum to {fmt(item_sum)} but the header says Total {fmt(total)}")
            crits = parse_criteria(block)
            qm = QUESTION_LINE_RE.search(context)
            key = qm.group(1).strip() if qm else context.split("Rubric", 1)[0][-200:]
            rubric_by_question[key].add(norm(block))
            for rubric in rubrics:
                if resolved in target_files(rubric, root) and rubric.get("match", "") in context:
                    if norm(expected_context(rubric, context)) != norm(context):
                        rep.error(path, f"seed {i}: ",
                                  f"context differs from {rubric['_path'].name}; run: python tools/rubrics.py stamp --write")

        for j, q, a in qa_pairs(seed):
            where = f"seed {i}, Q&A {j}: "
            questions[norm(q)] += 1
            answers[norm(a)] += 1
            if len(a.split()) < 3:
                rep.warn(path, where, "answer is very short")
            if not grading:
                continue

            if not q.lstrip().startswith(ANSWER_LABELS):
                rep.warn(path, where, "question does not start with 'Student Answer:'")
            gm = GRADE_RE.search(a)
            if not gm:
                rep.error(path, where, "no '**Grade:** x / y' line")
                continue
            got, out_of = float(gm.group(1)), float(gm.group(2))
            if total:
                grades.append(round(got / total, 6))
                if abs(out_of - total) > EPS:
                    rep.error(path, where, f"grade is out of {fmt(out_of)} but the rubric total is {fmt(total)}")
                if got < -EPS or got > total + EPS:
                    rep.error(path, where, f"grade {fmt(got)} is outside 0..{fmt(total)}")

            feedback = a.split("**Feedback:**", 1)
            if len(feedback) < 2 or not feedback[1].strip():
                rep.warn(path, where, "no '**Feedback:**' section")
                continue
            fb = feedback[1]
            low = fb.lower()
            for phrase in GENERIC_FEEDBACK:
                if phrase in low:
                    rep.warn(path, where, f"generic feedback ('{phrase}'); give a reason for each criterion")
            for h in HEDGES:
                if re.search(rf"\b{re.escape(h)}\b", low):
                    rep.warn(path, where, f"hedging word in feedback ('{h}')")

            if crits:
                check_criterion_lines(path, where, fb, crits, got, rep)
                continue
            pts = [float(x) for x in POINTS_RE.findall(fb)]
            if pts and total:
                earned = sum(p for p in pts if p > 0)
                lost = sum(p for p in pts if p < 0)
                if abs(earned - got) > EPS and abs(total + lost - got) > EPS:
                    rep.warn(path, where,
                             f"feedback points don't add up to the grade {fmt(got)} "
                             f"(earned items sum to {fmt(earned)}, total minus deductions is {fmt(total + lost)})")
            elif total and got not in (0.0, total):
                rep.warn(path, where, "feedback shows no point values, so the grade can't be checked")

    for text, count in questions.items():
        if count > 1 and text:
            rep.warn(path, "", f"question appears {count} times: {text[:60]}...")
    for text, count in answers.items():
        if count > 1 and text:
            rep.warn(path, "", f"answer appears {count} times: {text[:60]}...")
    for question, blocks in rubric_by_question.items():
        if len(blocks) > 1:
            rep.error(path, "", f"{len(blocks)} different rubric versions for the same question")

    if grades:
        most, n = Counter(grades).most_common(1)[0]
        if len(grades) >= 4 and n / len(grades) > 0.6:
            rep.warn(path, "", f"{n} of {len(grades)} examples score {most:.0%} of the total; vary the grades")
        if not any(g <= 0.25 + EPS for g in grades):
            rep.warn(path, "", "no low-scoring example (25% of the total or less)")
        if not any(abs(g - 1) < EPS for g in grades):
            rep.warn(path, "", "no full-score example")


def cmd_validate(args) -> int:
    root = Path(args.taxonomy)
    rep = Report()
    rubrics = load_rubrics(Path(args.rubric_dir))
    for rubric in rubrics:
        if "criteria" in rubric:
            for problem in check_rubric_file(rubric):
                rep.error(rubric["_path"], "", problem)
        else:
            total, items = rubric_items(rubric["block"])
            if total is None:
                rep.error(rubric["_path"], "", "no 'Rubric (Total N pts)' header")
            elif abs(sum(p for _, p in items) - total) > EPS:
                rep.error(rubric["_path"], "", f"items sum to {fmt(sum(p for _, p in items))}, header says {fmt(total)}")

    files = [Path(p) for p in args.paths] if args.paths else \
        sorted(p for p in root.rglob("qna.yaml") if ".git" not in p.parts)
    for path in files:
        validate_file(path, rubrics, root, rep)
    print(f"\nChecked {len(rubrics)} rubric file(s) and {len(files)} qna.yaml file(s): "
          f"{rep.errors} error(s), {rep.warnings} warning(s).")
    return 1 if rep.errors else 0


# --------------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--taxonomy", default=TAXONOMY_DEFAULT, help="taxonomy root (default: taxonomy)")
    parser.add_argument("--rubric-dir", default=RUBRIC_DIR_DEFAULT, help="rubric folder (default: data/rubrics)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("stamp", help="rebuild seed contexts from the rubric files")
    st.add_argument("--write", action="store_true", help="save the changes (default: only show them)")
    st.add_argument("--quiet", action="store_true", help="don't print diffs")
    st.set_defaults(func=cmd_stamp)

    va = sub.add_parser("validate", help="check rubric files and qna.yaml files")
    va.add_argument("paths", nargs="*", help="specific qna.yaml files (default: all under --taxonomy)")
    va.set_defaults(func=cmd_validate)

    ex = sub.add_parser("extract", help="create a block-only rubric file from an older qna.yaml")
    ex.add_argument("qna")
    ex.add_argument("--id", required=True, help="name for the rubric file")
    ex.add_argument("--match", help="text that identifies the context (default: its 'Question:' line)")
    ex.add_argument("--target", help="glob for the qna.yaml files it applies to")
    ex.add_argument("--force", action="store_true")
    ex.set_defaults(func=cmd_extract)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
