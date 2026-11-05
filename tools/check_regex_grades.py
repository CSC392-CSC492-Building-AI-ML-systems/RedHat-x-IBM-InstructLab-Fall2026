"""Mechanically check generated grades for the regex-construction grading skill.

For each generated example, the question is matched to one of the known languages below
(add more to QUESTIONS for new seed questions), and the student's regular expression is
tested against the real language on every string up to length 10.
The grade's C1 (soundness) and C2 (completeness) levels are then compared with the truth:

  C1: sound regex          -> must be "full"
      matches every string -> must be "none"
      otherwise unsound     -> must not be "full"
  C2: complete regex       -> must be "full"
      incomplete            -> must not be "full"

This is a lower bound on errors: it can't judge C3 (the explanation) or whether "partial"
vs "minimal" was the right choice. It also reports junk examples (the student answer is
a copy of the prompt, or uses symbols outside the question's alphabet) and totals that don't add up.

Usage:  python3 tools/check_regex_grades.py FILE.jsonl [FILE2.jsonl ...]
        add --show to print every example's verdict
"""

import itertools
import json
import re
import sys

# (pattern that identifies the question, alphabet, membership test)
QUESTIONS = [
    (r"even\s+number\s+of\s+0s", "01", lambda s: s.count("0") % 2 == 0),
    (r"end\s+with\s+01", "01", lambda s: s.endswith("01")),
    (r"length\s+is\s+a\s+multiple\s+of\s+3", "01", lambda s: len(s) % 3 == 0),
    (r"start\s+and\s+end\s+with\s+the\s+same\s+symbol", "ab", lambda s: len(s) > 0 and s[0] == s[-1]),
    (r"exactly\s+one\s+b", "ab", lambda s: s.count("b") == 1),
    (r"do\s+not\s+contain\s+00", "01", lambda s: "00" not in s),
]


def strings(alphabet):
    return [""] + ["".join(p) for n in range(1, 11) for p in itertools.product(alphabet, repeat=n)]
GRADE = re.compile(r"Grade:\**\s*([\d.]+)\s*/\s*([\d.]+)")
LEVEL = re.compile(r"C(\d)[^:\n]*:\s*\**\s*(full|partial|minimal|none)\s*\((\d+(?:\.\d+)?)\s*/\s*\d+\)")


def turn(rec, role):
    return next((m["content"] for m in rec["messages"] if m["role"] == role), "")


def check(rec):
    user, ans = turn(rec, "user"), turn(rec, "assistant")
    question = user.split("Rubric", 1)[0]
    found = [(a, f) for pat, a, f in QUESTIONS if re.search(pat, question)]
    if not found:
        return "unknown_question", None
    alphabet, member = found[0]
    STRINGS = strings(alphabet)
    IN_L = {s: member(s) for s in STRINGS}
    student = user.split("Student Answer:", 1)[-1].strip()
    if student.startswith("Grade the student answer") or len(student) < 5:
        return "junk_copied_prompt_or_empty", None
    m = re.match(r"r\s*=\s*([^\n]+)", student)
    if not m:
        return "no_regex_found", None
    rx = m.group(1).strip().rstrip(".").replace(" ", "")
    if set(rx) - set(alphabet + "+()*ε"):
        return "junk_off_topic_answer", rx
    try:
        r = re.compile("(?:" + rx.replace("+", "|").replace("ε", "") + r")\Z")
    except re.error:
        return "no_regex_found", rx
    acc = {s for s in STRINGS if r.match(s)}
    sound = all(IN_L[s] for s in acc)
    everything = len(acc) == len(STRINGS)
    complete = all(s in acc for s in STRINGS if IN_L[s])

    levels = {c: lv for c, lv, _ in LEVEL.findall(ans)}
    points = [float(p) for _, _, p in LEVEL.findall(ans)]
    g = GRADE.search(ans)
    problems = []
    if not g or len(points) != 3:
        problems.append("grade_unreadable_or_criteria_repeated")
    elif abs(sum(points) - float(g.group(1))) > 1e-9:
        problems.append("total_not_sum_of_criteria")
    c1, c2 = levels.get("1"), levels.get("2")
    if sound and c1 != "full":
        problems.append("C1_should_be_full")
    if everything and c1 != "none":
        problems.append("C1_should_be_none")
    if not sound and not everything and c1 == "full":
        problems.append("C1_full_but_unsound")
    if complete and c2 != "full":
        problems.append("C2_should_be_full")
    if not complete and c2 == "full":
        problems.append("C2_full_but_incomplete")
    return ("ok_C1_C2" if not problems else "wrong:" + ",".join(problems)), rx


def main(argv):
    show = "--show" in argv
    for path in [a for a in argv if a != "--show"]:
        counts = {}
        recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        for i, rec in enumerate(recs):
            verdict, rx = check(rec)
            key = "wrong" if verdict.startswith("wrong") else verdict
            counts[key] = counts.get(key, 0) + 1
            if show:
                print(f"  {i:3d} {verdict:45s} {rx or ''}")
        checked = counts.get("ok_C1_C2", 0) + counts.get("wrong", 0)
        print(f"\n== {path}")
        print(f"  examples: {len(recs)}")
        for k in sorted(counts):
            print(f"  {k:32s} {counts[k]}")
        if checked:
            print(f"  C1/C2 consistent with the regex: {counts.get('ok_C1_C2', 0)}/{checked} "
                  f"({100 * counts.get('ok_C1_C2', 0) / checked:.0f}%) of real answers;"
                  f" {counts.get('ok_C1_C2', 0)}/{len(recs)} of all examples")


if __name__ == "__main__":
    main(sys.argv[1:])
