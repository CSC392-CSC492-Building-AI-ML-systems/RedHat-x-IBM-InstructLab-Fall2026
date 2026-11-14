"""Drop grade-first answers that don't read like a student's, before combining for training.

In the first full run, 22 of 603 answers (3.6%) contained the teacher drafting or talking about
its task instead of a student's answer: "Wait, re-check sum", "? No, that adds extra 1s", or "The
prompt says ...". Most came from a few reference answers that every answer built on them copied.
All six "larger_c" scenario answers were like this, because their instruction asked for a proof
of something false (fixed in grade_first_extras.py since). The generator now rejects such text,
so newer runs shouldn't need this, but it's safe to run on any grade-first output.

Run on the output folder of jobs/generate_data.sh (OUT), or on one run folder inside it:
    python3 tools/clean_grade_first.py data/generated/grade_first_2026-11-14 --drop-scenario larger_c
    python3 tools/clean_grade_first.py OUT --dry-run          # only report what would be dropped
    python3 tools/clean_grade_first.py OUT --drop-unconfirmed # also drop answers whose level wasn't confirmed

It rewrites node_datasets_*/compositional_skills_*.jsonl (what combine_sdg.py --full-skills
reads) and keeps the originals in node_datasets_*/original/. Running it again starts from the
originals, so the options of the last run are the ones that apply. A report goes to
clean_report.json in the run folder.
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grade_first_extras as gx  # noqa: E402

RUN_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")


def run_folder(path):
    if RUN_DIR.match(os.path.basename(os.path.normpath(path))):
        return path
    runs = sorted(d for d in os.listdir(path) if RUN_DIR.match(d) and os.path.isdir(os.path.join(path, d)))
    if not runs:
        raise SystemExit(f"ERROR: no run folder (like 2026-11-14_125241) in {path}")
    return os.path.join(path, runs[-1])


def student_answer(rec):
    user = next((m["content"] for m in rec.get("messages", []) if m["role"] == "user"), rec.get("question", ""))
    return user.split("Student Answer:", 1)[1].strip() if "Student Answer:" in user else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="the OUT folder of the run, or a run folder inside it")
    ap.add_argument("--drop-scenario", nargs="*", default=[], metavar="NAME",
                    help="also drop every answer of these scenarios (e.g. larger_c)")
    ap.add_argument("--drop-unconfirmed", action="store_true",
                    help="also drop answers with a criterion in the unconfirmed column")
    ap.add_argument("--dry-run", action="store_true", help="report only; change nothing")
    a = ap.parse_args()

    run = run_folder(a.folder)
    files = sorted(glob.glob(os.path.join(run, "node_datasets_*", "compositional_skills_*.jsonl")))
    if not files:
        raise SystemExit(f"ERROR: no node_datasets_*/compositional_skills_*.jsonl in {run}")
    report = {"run": run, "options": {"drop_scenario": a.drop_scenario, "drop_unconfirmed": a.drop_unconfirmed},
              "skills": {}, "dropped": []}
    total_in = total_out = 0
    for path in files:
        backup = os.path.join(os.path.dirname(path), "original", os.path.basename(path))
        source = backup if os.path.exists(backup) else path
        with open(source, encoding="utf-8") as fh:
            recs = [json.loads(line) for line in fh if line.strip()]
        keep = []
        for r in recs:
            why = gx.text_problem(student_answer(r))
            if not why and r.get("scenario") in a.drop_scenario:
                why = f"scenario {r['scenario']}"
            if not why and a.drop_unconfirmed and r.get("unconfirmed"):
                why = f"level unconfirmed for {r['unconfirmed']}"
            if why:
                report["dropped"].append({"id": r.get("cand_id"), "why": why})
            else:
                keep.append(r)
        skill = re.sub(r"\.jsonl$", "", os.path.basename(path).split("csc236_")[-1])
        report["skills"][skill] = {"before": len(recs), "after": len(keep)}
        total_in, total_out = total_in + len(recs), total_out + len(keep)
        print(f"{skill:24s} {len(recs):4d} -> {len(keep):4d}")
        if not a.dry_run:
            if source == path:
                os.makedirs(os.path.dirname(backup), exist_ok=True)
                shutil.copy2(path, backup)
            with open(path, "w", encoding="utf-8") as fh:
                for r in keep:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{'total':24s} {total_in:4d} -> {total_out:4d}")
    for d in report["dropped"]:
        print(f"  dropped {d['id']}: {d['why']}")
    if a.dry_run:
        print("dry run: nothing changed")
    else:
        with open(os.path.join(run, "clean_report.json"), "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"originals kept in node_datasets_*/original/; report in {os.path.join(run, 'clean_report.json')}")


if __name__ == "__main__":
    main()
