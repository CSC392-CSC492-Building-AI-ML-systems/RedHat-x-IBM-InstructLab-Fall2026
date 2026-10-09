# GradeAI

GradeAI is a grading assistant for university proof courses. A small language model, running locally, grades student proofs against the course rubric, explains the score for each part, and flags grades it is unsure about for a TA to check. Student work never leaves the machine. The model is fine-tuned with InstructLab.

Red Hat × IBM InstructLab project, Fall 2026.

## Repository layout

| Folder | Contents | Milestone |
| --- | --- | --- |
| `env/` | Python environments | M1 |
| `jobs/` | Scripts for running work on the cluster | M1, M6, M7 |
| `rubrics/` | Grading rubrics | M1 |
| `taxonomy/` | InstructLab taxonomy | M3 |
| `data/` | Synthetic training data | M4 |
| `test_set/` | Test set | M5 |
| `training/` | Fine-tuning settings | M6 |
| `eval/` | Evaluation code | M7 |
| `results/` | Evaluation results | M7 |
| `app/` | Prototype interface | M8 |
| `docs/` | Setup guide and decisions | — |

## Not in git

Model files, generated data and Python environments are too large for git. They're stored on the cluster.
