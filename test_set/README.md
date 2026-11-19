# test_set

This test set evaluates how accurately GradeAI grades CSC236 mathematical proofs using predefined rubrics. It contains student-style proofs with criterion-level reference scores (ground-truth labels). The test sets were generated using Claude Opus 5.5 and the InstructLab teacher model, with AI-assisted validation and team review.

### Group A — Familiar Questions (40 cases)

Evaluates grading accuracy on questions and rubrics similar to those used during training, using separate student answers for evaluation.

### Group B — Unseen Questions (101 cases)

Evaluates the model's ability to grade proofs for questions not directly used during training, measuring its generalization to new problems.

Group B v4 (`groupB_v4_101.json`) is the default evaluation dataset, containing 101 cases across 32 unique questions. It includes original student answers and variants designed to test grading sensitivity, robustness, paraphrase consistency, and fairness.

### Usage

The test sets are kept separate from model training and are used only for evaluation. Once finalized, they are frozen to ensure consistent and reproducible results.

Part of Milestone 5.