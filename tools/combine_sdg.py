"""Combine per-topic ilab data generation outputs into one pair of training files.

For each topic folder under ROOT (e.g. data/generated/qwen3-30b-instruct-2507/induction),
uses the NEWEST run folder (named like 2026-10-26_123649) and joins:
  knowledge_train_msgs_*.jsonl  ->  OUT/knowledge_train_msgs.jsonl   (phase 1)
  skills_train_msgs_*.jsonl     ->  OUT/skills_train_msgs.jsonl      (phase 2)
Lines are shuffled with a fixed seed so the result is reproducible.

--fix-repeated-context: in skill examples, sdg repeats the rubric/context after the student
submission. This keeps only the first copy (everything from the second copy of the prompt's
first line onward is removed).

Writes OUT/manifest.json listing the source files, line counts and settings.

Usage:
  python3 tools/combine_sdg.py ROOT OUT [--fix-repeated-context] [--skip name ...]
"""

import argparse
import glob
import json
import os
import random
import re

RUN_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")


def newest_run(topic_dir):
    runs = sorted(d for d in os.listdir(topic_dir)
                  if RUN_DIR.match(d) and os.path.isdir(os.path.join(topic_dir, d)))
    return os.path.join(topic_dir, runs[-1]) if runs else None


def fix_context(record):
    changed = False
    for m in record.get("messages", []):
        if m.get("role") != "user":
            continue
        text = m["content"]
        first = text.split("\n", 1)[0].strip()
        if len(first) < 20:            # too short to be a reliable marker
            continue
        second = text.find(first, len(first))
        if second > 0:
            m["content"] = text[:second].rstrip() + "\n"
            changed = True
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("out")
    ap.add_argument("--fix-repeated-context", action="store_true")
    ap.add_argument("--skip", nargs="*", default=[], help="topic folders to leave out")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    manifest = {"root": os.path.abspath(a.root), "seed": a.seed,
                "fix_repeated_context": a.fix_repeated_context, "sources": {}, "totals": {}}
    combined = {"knowledge_train_msgs": [], "skills_train_msgs": []}
    fixed = 0

    for topic in sorted(os.listdir(a.root)):
        tdir = os.path.join(a.root, topic)
        if not os.path.isdir(tdir) or topic in a.skip:
            continue
        run = newest_run(tdir)
        if not run:
            print(f"skip  {topic}: no run folder")
            continue
        for kind in combined:
            files = sorted(glob.glob(os.path.join(run, f"{kind}_*.jsonl")))
            for f in files:
                n = 0
                with open(f, encoding="utf-8") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        if a.fix_repeated_context and fix_context(rec):
                            fixed += 1
                        combined[kind].append(json.dumps(rec, ensure_ascii=False))
                        n += 1
                manifest["sources"].setdefault(topic, {})[os.path.relpath(f, a.root)] = n
                print(f"{topic:28s} {kind:22s} {n:7d}  ({os.path.relpath(f, a.root)})")

    rng = random.Random(a.seed)
    for kind, lines in combined.items():
        rng.shuffle(lines)
        path = os.path.join(a.out, f"{kind}.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + ("\n" if lines else ""))
        manifest["totals"][kind] = len(lines)
        print(f"wrote {path}: {len(lines)} examples")
    manifest["repeated_context_fixed"] = fixed
    if a.fix_repeated_context:
        print(f"fixed repeated context in {fixed} examples")
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


if __name__ == "__main__":
 """Combine per-topic ilab data generation outputs into one pair of training files.

For each topic folder under ROOT (e.g. data/generated/qwen3-30b-instruct-2507/induction),
uses the NEWEST run folder (named like 2026-10-26_123649) and joins:
  knowledge_train_msgs_*.jsonl  ->  OUT/knowledge_train_msgs.jsonl   (phase 1)
  skills_train_msgs_*.jsonl     ->  OUT/skills_train_msgs.jsonl      (phase 2)
Lines are shuffled with a fixed seed so the result is reproducible.

Optional cleanup (applied to the skills file only):
  --fix-repeated-context  sdg repeats the rubric/context after the student submission in skill
                          prompts. Keep only the first copy.
  --clean-grades          For grading examples (an answer with "Grade: x / y"):
                            - drop examples with no readable grade, or whose "out of" differs
                              from the rubric's "Total N pts";
                            - when the same prompt appears several times, keep ONE example if
                              at least 2/3 of its copies agree on the grade (the majority grade),
                              otherwise drop all copies (the teacher couldn't grade it consistently).
  --dedupe                Drop exact duplicate examples, and keep one example per repeated
                          non-grading prompt.
  --full-skills           ilab keeps only 30 examples per skill in skills_train_msgs (NUM_SYNTH_SKILLS).
                          With this, skill runs contribute every generated example instead, read from
                          node_datasets_*/compositional_skills_*.jsonl. Knowledge runs are unchanged.
  --drop-prefix TEXT ...  Drop examples whose prompt starts with any of these texts
                          (e.g. "Write in LaTeX" to leave out a skill).

Writes OUT/manifest.json listing the source files, line counts, settings and what was removed.

Usage:
  python3 tools/combine_sdg.py ROOT OUT [--fix-repeated-context] [--clean-grades] [--dedupe]
                               [--drop-prefix TEXT ...] [--skip name ...]
"""

import argparse
import collections
import glob
import json
import os
import random
import re

RUN_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
GRADE = re.compile(r"Grade:?\**\s*([\d.]+)\s*/\s*([\d.]+)")
TOTAL = re.compile(r"Total\s+([\d.]+)\s*pts?")


def newest_run(topic_dir):
    runs = sorted(d for d in os.listdir(topic_dir)
                  if RUN_DIR.match(d) and os.path.isdir(os.path.join(topic_dir, d)))
    return os.path.join(topic_dir, runs[-1]) if runs else None


def turn(rec, role):
    return next((m["content"] for m in rec.get("messages", []) if m.get("role") == role), "")


def fix_context(record):
    changed = False
    for m in record.get("messages", []):
        if m.get("role") != "user":
            continue
        text = m["content"]
        first = text.split("\n", 1)[0].strip()
        if len(first) < 20:            # too short to be a reliable marker
            continue
        second = text.find(first, len(first))
        if second > 0:
            m["content"] = text[:second].rstrip() + "\n"
            changed = True
    return changed


def is_grading(rec):
    user, ans = turn(rec, "user"), turn(rec, "assistant")
    return bool(GRADE.search(ans)) or "Grade the student" in user or bool(TOTAL.search(user))


def clean(records, a, stats):
    """records: list of dicts. Returns the cleaned list; counts go into stats."""
    out = []
    if a.drop_prefix:
        kept = []
        for r in records:
            if turn(r, "user").lstrip().startswith(tuple(a.drop_prefix)):
                stats["dropped_by_prefix"] += 1
            else:
                kept.append(r)
        records = kept

    grading, other = [], []
    for r in records:
        (grading if a.clean_grades and is_grading(r) else other).append(r)

    if a.clean_grades:
        by_prompt = collections.defaultdict(list)
        for r in grading:
            g = GRADE.search(turn(r, "assistant"))
            t = TOTAL.search(turn(r, "user"))
            if not g:
                stats["grading_no_readable_grade"] += 1
                continue
            if t and float(t.group(1)) != float(g.group(2)):
                stats["grading_total_mismatch"] += 1
                continue
            by_prompt[turn(r, "user")].append((float(g.group(1)), r))
        for prompt, items in by_prompt.items():
            if len(items) == 1:
                out.append(items[0][1])
                continue
            counts = collections.Counter(score for score, _ in items)
            score, c = counts.most_common(1)[0]
            if c * 3 >= len(items) * 2:
                out.append(next(r for s, r in items if s == score))
                stats["grading_duplicates_removed"] += len(items) - 1
            else:
                stats["grading_inconsistent_prompts_dropped"] += 1
                stats["grading_inconsistent_examples_dropped"] += len(items)

    if a.dedupe:
        seen_exact, seen_prompt = set(), set()
        for r in other:
            key = json.dumps(r.get("messages"), sort_keys=True)
            prompt = turn(r, "user")
            if key in seen_exact or prompt in seen_prompt:
                stats["duplicates_removed"] += 1
                continue
            seen_exact.add(key)
            seen_prompt.add(prompt)
            out.append(r)
    else:
        out.extend(other)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("out")
    ap.add_argument("--fix-repeated-context", action="store_true")
    ap.add_argument("--clean-grades", action="store_true")
    ap.add_argument("--dedupe", action="store_true")
    ap.add_argument("--drop-prefix", nargs="*", default=[])
    ap.add_argument("--full-skills", action="store_true",
                    help="for skill runs, use every generated example instead of ilab's 30-per-skill sample")
    ap.add_argument("--skip", nargs="*", default=[], help="topic folders to leave out")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    manifest = {"root": os.path.abspath(a.root), "seed": a.seed,
                "options": {"fix_repeated_context": a.fix_repeated_context,
                            "clean_grades": a.clean_grades, "dedupe": a.dedupe,
                            "drop_prefix": a.drop_prefix, "skip": a.skip,
                            "full_skills": a.full_skills},
                "sources": {}, "totals": {}, "removed": {}}
    combined = {"knowledge_train_msgs": [], "skills_train_msgs": []}
    fixed = 0

    for topic in sorted(os.listdir(a.root)):
        tdir = os.path.join(a.root, topic)
        if not os.path.isdir(tdir) or topic in a.skip:
            continue
        run = newest_run(tdir)
        if not run:
            print(f"skip  {topic}: no run folder")
            continue
        for kind in combined:
            files = sorted(glob.glob(os.path.join(run, f"{kind}_*.jsonl")))
            if kind == "skills_train_msgs" and a.full_skills:
                # ilab samples each skill down to 30 examples (NUM_SYNTH_SKILLS) when mixing;
                # the full generated set for each skill is in node_datasets_*/.
                full = sorted(glob.glob(os.path.join(run, "node_datasets_*", "compositional_skills_*.jsonl")))
                if full:
                    files = full
            for f in files:
                n = 0
                with open(f, encoding="utf-8") as fh:
                    for line in fh:
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        if a.fix_repeated_context and fix_context(rec):
                            fixed += 1
                        combined[kind].append(rec)
                        n += 1
                manifest["sources"].setdefault(topic, {})[os.path.relpath(f, a.root)] = n
                print(f"{topic:28s} {kind:22s} {n:7d}  ({os.path.relpath(f, a.root)})")

    rng = random.Random(a.seed)
    for kind, records in combined.items():
        stats = collections.Counter()
        # Cleanup applies to the skills file only: the knowledge mix can repeat examples on
        # purpose (sdg's recipe up-samples some datasets).
        if kind == "skills_train_msgs":
            records = clean(records, a, stats)
        rng.shuffle(records)
        path = os.path.join(a.out, f"{kind}.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        manifest["totals"][kind] = len(records)
        manifest["removed"][kind] = dict(stats)
        print(f"wrote {path}: {len(records)} examples")
        for k, v in sorted(stats.items()):
            print(f"    {k}: {v}")
    manifest["repeated_context_fixed"] = fixed
    if a.fix_repeated_context:
        print(f"fixed repeated context in {fixed} examples")
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


if __name__ == "__main__":
    main()   main()
