"""Convert skill qna.yaml files written in the knowledge format to ilab's skill format.

Knowledge format (rejected for skills):          Skill format (version 2):
  version: 3                                        version: 2
  domain: ...                                       task_description: ...
  seed_examples:                                    seed_examples:
    - context: <rubric>                               - context: <rubric>
      questions_and_answers:                            question: <submission 1>
        - question: <submission 1>                      answer: <grade 1>
          answer: <grade 1>                           - context: <rubric>
        - question: <submission 2> ...                  question: <submission 2> ...

Each question/answer pair becomes its own seed example with its context repeated.
Text is kept as is, except trailing spaces are removed (ilab's linter rejects them).

Usage:
  python3 tools/convert_skill_yaml.py taxonomy/compositional_skills/**/qna.yaml          # dry run
  python3 tools/convert_skill_yaml.py --write taxonomy/compositional_skills/**/qna.yaml  # rewrite files
"""

import sys

import yaml

MIN_SEEDS = 5


class _Dumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):  # indent list items under their key
        return super().increase_indent(flow, False)


def _str(dumper, s):
    style = "|" if "\n" in s else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style=style)


_Dumper.add_representer(str, _str)


def clean(text):
    if not isinstance(text, str):
        return text
    lines = [line.rstrip() for line in text.splitlines()]
    out = "\n".join(lines).strip("\n")
    return out + "\n" if "\n" in out or text.endswith("\n") else out


def convert(data):
    """Return (new_data, notes) or (None, reason) if nothing to do."""
    if not isinstance(data, dict) or "seed_examples" not in data:
        return None, "no seed_examples"
    needs = data.get("version") != 2 or "domain" in data or any(
        "questions_and_answers" in s for s in data["seed_examples"])
    if not needs:
        return None, "already in skill format"

    seeds = []
    for s in data["seed_examples"]:
        if "questions_and_answers" in s:
            for qa in s["questions_and_answers"]:
                seed = {}
                if s.get("context"):
                    seed["context"] = clean(s["context"])
                seed["question"] = clean(qa["question"])
                seed["answer"] = clean(qa["answer"])
                seeds.append(seed)
        else:
            seeds.append({k: clean(s[k]) for k in ("context", "question", "answer") if k in s})

    out = {
        "version": 2,
        "created_by": data.get("created_by", "<github-username>"),
        "task_description": clean(data.get("task_description", "")),
        "seed_examples": seeds,
    }
    notes = [f"{len(seeds)} seed examples"]
    if len(seeds) < MIN_SEEDS:
        notes.append(f"WARNING: ilab needs at least {MIN_SEEDS}")
    missing = [i + 1 for i, s in enumerate(seeds) if not {"question", "answer"} <= set(s)]
    if missing:
        notes.append(f"WARNING: seeds {missing} lack a question or answer")
    return out, "; ".join(notes)


def main(argv):
    write = "--write" in argv
    paths = [a for a in argv if a != "--write"]
    if not paths:
        print(__doc__)
        return 1
    for p in paths:
        try:
            data = yaml.safe_load(open(p, encoding="utf-8"))
        except yaml.YAMLError as e:
            mark = getattr(e, "problem_mark", None)
            where = f" line {mark.line + 1}, col {mark.column + 1}" if mark else ""
            print(f"FAIL     {p}: YAML syntax error{where} - fix it by hand first")
            continue
        new, note = convert(data)
        if new is None:
            print(f"skip     {p}: {note}")
            continue
        text = yaml.dump(new, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=10**9)
        if write:
            with open(p, "w", encoding="utf-8") as f:
                f.write(text if text.endswith("\n") else text + "\n")
            print(f"written  {p}: {note}")
        else:
            print(f"would    {p}: {note}  (dry run; add --write to change files)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
