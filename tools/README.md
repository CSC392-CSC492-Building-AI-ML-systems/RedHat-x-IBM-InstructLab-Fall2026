# tools

Scripts we use to prepare seed files and process generated data. Run them from the repository
root.

| Script | What it does | When to use it |
| --- | --- | --- |
| `rubrics.py` | Builds grading seed contexts from the rubric files in `data/rubrics/`, and checks the grading seeds | After editing a rubric or a grading `qna.yaml`, and before data generation |
| `convert_skill_yaml.py` | Converts skill `qna.yaml` files written in the knowledge format (`version: 3`, `questions_and_answers`) to ilab's skill format (`version: 2`) | When a skill file uses the knowledge layout and `ilab` rejects it |
| `combine_sdg.py` | Joins the newest generation run of each topic into one knowledge file and one skills file, shuffled with a fixed seed | After `ilab data generate`, before training |

## rubrics.py

Each grading question has one rubric file in `data/rubrics/`, which is the only place to edit it.
The script copies the question and rubric into every seed `context` that uses it, then checks the
seeds. See [`data/rubrics/README.md`](../data/rubrics/README.md) for the rubric format.

```bash
pip install ruamel.yaml
python3 tools/rubrics.py stamp            # show which contexts differ from their rubric file
python3 tools/rubrics.py stamp --write    # update them
python3 tools/rubrics.py validate         # check rubric files and seeds
```

`validate` exits with an error if a seed's level or points don't match its rubric, if the
criterion points don't add up to the grade, if a context has drifted from its rubric file, or if a
file has trailing spaces, a `<|...|>` token or a placeholder `created_by`. It warns about lines
over 120 characters, missing `attribution.txt` files and grades that are all the same.

## convert_skill_yaml.py

Each question/answer pair becomes its own seed example with its context repeated. Trailing spaces
are removed, because ilab's linter rejects them.

```bash
python3 tools/convert_skill_yaml.py taxonomy/compositional_skills/**/qna.yaml           # dry run
python3 tools/convert_skill_yaml.py --write taxonomy/compositional_skills/**/qna.yaml   # rewrite
```

## combine_sdg.py

For each topic folder under ROOT, uses the newest run folder (named like `2026-10-26_123649`) and
writes `OUT/knowledge_train_msgs.jsonl` (phase 1), `OUT/skills_train_msgs.jsonl` (phase 2) and
`OUT/manifest.json`.

```bash
python3 tools/combine_sdg.py ROOT OUT [--fix-repeated-context] [--skip name ...] [--seed 42]
```

`--fix-repeated-context` removes the second copy of the rubric and question that sdg adds after the
student answer in skill examples. It finds the copy by the prompt's first line, so grading contexts
should start with a long, fixed first line, as the ones built by `rubrics.py` do.