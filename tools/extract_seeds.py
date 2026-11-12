"""Read the grading seeds in taxonomy/.../grading/csc236/<topic>/qna.yaml into one JSON file.

It needs only the Python standard library, so it runs in any environment. The qna.yaml files
use block literals with a fixed layout, which are read directly instead of with pyyaml. Each
rubric is also split into its criteria (id, name, max, and each level's points and text) and
checked. Full must equal the maximum, the points must go down level by level, and none must be 0.

    python3 tools/extract_seeds.py REPO_DIR OUT.json topic1 topic2 ...
"""
import json
import re
import sys
from pathlib import Path

LEVELS = ("full", "partial", "minimal", "none")


def block_literals(path):
    """The seed_examples of a qna.yaml: a list of {context, question, answer}."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    seeds, cur, key, buf = [], None, None, []

    def flush():
        if cur is not None and key is not None:
            cur[key] = "\n".join(buf).rstrip("\n") + "\n"

    for line in lines:
        m = re.match(r"^(  - |    )(context|question|answer): \|\s*$", line)
        if m:
            flush()
            if m.group(1) == "  - ":
                cur = {}
                seeds.append(cur)
            key, buf = m.group(2), []
            continue
        if key is not None and (line.startswith("      ") or not line.strip()):
            buf.append(line[6:] if line.strip() else "")
            continue
        if key is not None:  # any other line ends the block
            flush()
            key, buf = None, []
    flush()
    return seeds


def parse_rubric(context):
    """Criteria and general rules from a seed context."""
    question = context.split("Question:\n", 1)[1].split("\n\nRubric (Total", 1)[0].strip()
    rubric_text = "Rubric (Total" + context.split("Rubric (Total", 1)[1]
    total = float(re.match(r"Rubric \(Total (\d+(?:\.\d+)?) pts\)", rubric_text).group(1))
    body, _, rules = rubric_text.partition("\nGeneral rules:\n")
    criteria = []
    for block in re.split(r"\n(?=- C\d+ )", body.split("\n", 1)[1]):
        head = re.match(r"- (C\d+) (.+?): (\d+(?:\.\d+)?) pts\.", block)
        if not head:
            raise ValueError(f"can't read criterion header: {block[:80]!r}")
        levels = {}
        parts = re.split(r"\n\s+(?=(?:full|partial|minimal|none) \(\d+(?:\.\d+)?\):)", block)
        for p in parts[1:]:
            lm = re.match(r"(full|partial|minimal|none) \((\d+(?:\.\d+)?)\):\s*(.*)", p, re.S)
            levels[lm.group(1)] = {"points": float(lm.group(2)),
                                   "text": re.sub(r"\s+", " ", lm.group(3)).strip()}
        criteria.append({"id": head.group(1), "name": head.group(2), "max": float(head.group(3)),
                         "levels": levels})
    for c in criteria:
        if tuple(c["levels"]) != LEVELS:
            raise ValueError(f"{c['id']} levels are {list(c['levels'])}")
        pts = [c["levels"][lv]["points"] for lv in LEVELS]
        if pts[0] != c["max"] or pts[-1] != 0 or any(a <= b for a, b in zip(pts, pts[1:])):
            raise ValueError(f"{c['id']} level points {pts} don't fit max {c['max']}")
    if sum(c["max"] for c in criteria) != total:
        raise ValueError(f"criteria maxima don't add up to {total}")
    rule_list = [re.sub(r"\s+", " ", r).strip()
                 for r in re.split(r"\n(?=\d+\. )", rules.strip()) if r.strip()]
    return question, rubric_text.rstrip("\n"), criteria, rule_list


def main():
    repo, out, topics = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
    result = []
    for topic in topics:
        path = repo / "taxonomy/compositional_skills/grounded/grading/csc236" / topic / "qna.yaml"
        for n, s in enumerate(block_literals(path), 1):
            question, rubric_text, criteria, rules = parse_rubric(s["context"])
            result.append({"seed_id": f"{topic}_{n:02d}", "topic": topic, "context": s["context"],
                           "question": question, "rubric_text": rubric_text, "criteria": criteria,
                           "general_rules": rules, "seed_answer": s["question"], "seed_grade": s["answer"]})
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(result)} seeds from {len(topics)} topics -> {out}")


if __name__ == "__main__":
    main()
