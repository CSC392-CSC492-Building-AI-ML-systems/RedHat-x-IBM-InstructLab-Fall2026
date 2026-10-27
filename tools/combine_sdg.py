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
    main()
