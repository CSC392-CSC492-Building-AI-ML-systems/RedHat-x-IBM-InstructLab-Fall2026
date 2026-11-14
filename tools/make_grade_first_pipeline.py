"""Make the grade_first pipeline folder for `ilab data generate --pipeline`.

ilab needs three files in a pipeline folder. knowledge.yaml and freeform_skills.yaml are ilab's
own "full" pipelines, copied with their prompt-file paths made absolute. grounded_skills.yaml is
replaced: it runs the grade-first blocks from tools/grade_first_blocks.py, which build graded
answers the way tools/gen_answers.py does. Grading skills are grounded skills, so they go through
grounded_skills.yaml.

Run once, in the ilab environment, from the repo folder:
    python3 tools/make_grade_first_pipeline.py                 # writes pipelines/grade_first
    python3 tools/make_grade_first_pipeline.py --refs 5 --per-question 13 --workers 32
    python3 tools/make_grade_first_pipeline.py --no-extras --refs 3 --out pipelines/grade_first_plain

--per-question "scaled" (the default) uses ilab's --sdg-scale-factor as the number of answers
per question. By default the blocks also use tools/grade_first_extras.py (more kinds of
mistakes, whole-answer mistakes and more answer styles); --no-extras gives exactly what
tools/gen_answers.py makes. The folder also gets a CUSTOM_BLOCKS file, which tells jobs/generate_data.sh to
run ilab through tools/ilab_grade_first.py.
"""

import argparse
import importlib.util
import os

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def full_pipeline_dir():
    spec = importlib.util.find_spec("instructlab.sdg")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit(
            "ERROR: instructlab.sdg isn't installed here. Activate the ilab environment first."
        )
    return os.path.join(list(spec.submodule_search_locations)[0], "pipelines", "full")


def absolute_paths(node, base):
    """Make every relative config_path / config_paths absolute, relative to base."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "config_path" and isinstance(v, str) and not os.path.isabs(v):
                node[k] = os.path.normpath(os.path.join(base, v))
            elif k == "config_paths" and isinstance(v, list):
                node[k] = [
                    os.path.normpath(os.path.join(base, p))
                    if isinstance(p, str) and not os.path.isabs(p)
                    else p
                    for p in v
                ]
            else:
                absolute_paths(v, base)
    elif isinstance(node, list):
        for item in node:
            absolute_paths(item, base)
    return node


def grounded_pipeline(a):
    common = {"repo": REPO}
    extras = {"extras": not a.no_extras}
    return {
        "version": "1.0",
        "blocks": [
            {
                "name": "match_seed_questions",
                "type": "GradeFirstSeeds",
                "config": dict(common),
            },
            {
                "name": "write_reference_answers",
                "type": "GradeFirstReferences",
                "config": {
                    **common,
                    **extras,
                    "refs": a.refs,
                    "workers": a.workers,
                    "seed": a.seed,
                },
            },
            {
                "name": "choose_grades_first",
                "type": "GradeFirstTargets",
                "config": {
                    **common,
                    **extras,
                    "per_question": a.per_question,
                    "seed": a.seed,
                },
            },
            {
                "name": "build_answers",
                "type": "GradeFirstAnswers",
                "config": {**common, **extras, "workers": a.workers, "seed": a.seed},
            },
            {
                "name": "write_labels",
                "type": "GradeFirstLabels",
                "config": {**common, "workers": a.workers, "seed": a.seed},
            },
            {
                "name": "drop_failed_answers",
                "type": "FilterByValueBlock",
                "config": {
                    "filter_column": "failed",
                    "filter_value": "",
                    "operation": "eq",
                },
                "drop_columns": [
                    "failed",
                    "ref_json",
                    "answer",
                    "changes_json",
                    "prebuilt",
                ],
            },
        ],
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default=os.path.join(REPO, "pipelines", "grade_first"))
    ap.add_argument(
        "--refs",
        type=int,
        default=5,
        help="correct reference answers per question (default 5)",
    )
    ap.add_argument(
        "--no-extras",
        action="store_true",
        help="only what gen_answers.py does: no extra mistakes, scenarios or styles",
    )
    ap.add_argument(
        "--per-question",
        default="scaled",
        help='answers per question, or "scaled" for --sdg-scale-factor (default)',
    )
    ap.add_argument(
        "--workers", type=int, default=32, help="parallel requests to the teacher"
    )
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    if a.per_question != "scaled":
        a.per_question = int(a.per_question)

    src = full_pipeline_dir()
    os.makedirs(a.out, exist_ok=True)
    for name in ("knowledge.yaml", "freeform_skills.yaml"):
        with open(os.path.join(src, name), encoding="utf-8") as fh:
            content = absolute_paths(yaml.safe_load(fh), src)
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as fh:
            yaml.safe_dump(content, fh, sort_keys=False)
    with open(os.path.join(a.out, "grounded_skills.yaml"), "w", encoding="utf-8") as fh:
        fh.write(
            "# Grade-first generation for the CSC236 grading skills (tools/grade_first_blocks.py).\n"
            "# Run ilab through tools/ilab_grade_first.py so these block types are registered.\n"
        )
        yaml.safe_dump(grounded_pipeline(a), fh, sort_keys=False)
    with open(os.path.join(a.out, "CUSTOM_BLOCKS"), "w", encoding="utf-8") as fh:
        fh.write("tools/grade_first_blocks.py\n")
    for name in (
        "knowledge.yaml",
        "freeform_skills.yaml",
        "grounded_skills.yaml",
        "CUSTOM_BLOCKS",
    ):
        print(f"wrote {os.path.join(a.out, name)}")


if __name__ == "__main__":
    main()
