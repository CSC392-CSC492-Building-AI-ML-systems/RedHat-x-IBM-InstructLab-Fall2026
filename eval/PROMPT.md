# Evaluation prompt

Template `eval-prompt-v3`, built by [`prompt.py`](prompt.py). The base model and the fine-tuned model get exactly the same messages for every test case.

> **Status:** the student-answer layout is **provisional** (`LAYOUT_VERIFIED = False`). It has not yet been checked against real training data on Fir; see [Open points](#open-points). The Group B labels it is scored against are also provisional: draft v3, AI-drafted and human-reviewed, but not independently TA-verified or frozen.

## What the model sees

Each case becomes two chat messages.

1. **System:** the system message InstructLab puts in every training example. It is the same text `training/compare_adapter.py` uses.
2. **User:**

```
Grade the student answer against the question and rubric below. For each criterion,
choose the level that fits the answer and give a one-sentence reason.

Question:
<question, as stored in the test set>

Rubric (Total <N> pts):
- C1 <criterion>: <max> pts.
  full (<pts>): <expectation>
  partial (<pts>): <expectation>
  minimal (<pts>): <expectation>
  none (0): <expectation>
- C2 ...
General rules:
1. <grading_policies[0]>
2. <grading_policies[1]>
3. <grading_policies[2]>
4. <grading_policies[3]>

Write your grade in exactly this format, with exactly these criterion lines, and nothing else:

**Feedback:**
- C1 <criterion>: <level> (<points>/<max>). <one-sentence reason>
- C2 ...   (one line for each criterion in this rubric)
Total: <C1 points> + <C2 points> + ... = <total points>.

**Grade:** <total points> / <N>

<level> is full, partial, minimal or none, and <points> is what the rubric gives that level. The Grade must equal the sum of all criterion points.

Student Answer:
<student_answer, verbatim>
```

From each test case, only `question`, `rubric` and `student_answer` are used. `prompt.build_messages` rejects any other field. The general rules are the same four for every case.

The student answer is passed through unchanged. Some answers contain errors, prompt-injection text or fake grades on purpose, and cleaning them would defeat those tests. The answer comes after the grading instructions, under its own `Student Answer:` heading (Ethics §4 mitigation).

To print the exact prompt for a case:

```bash
python3 -m eval.prompt csc236_B_cind_01_ans01
```

The rendered prompts are not copied into this file, so that test-set text doesn't spread to more places in the repo.

## How it relates to the training prompt

The question, rubric and instruction are rendered the same way as the grading seeds. `prompt.py` has its own copy of the rendering code from `tools/rubrics.py`.

The tests pin the exact text this copy produces for a fixed input, but they don't compare it with `tools/rubrics.py`, `data/rubrics/` or the taxonomy. A change to the training rendering won't fail a test, so compare the rendering again during the layout check below.

These differences are deliberate:

| # | Training seeds | Evaluation prompt | Why |
|---|---|---|---|
| 1 | `General rules:` holds each question's own rules (e.g., "The question requires simple induction…") plus the standard rules. | `General rules:` holds the dataset's 4 `grading_policies`, the same for every case. | Group B has no per-question rules. The labels were written under these policies, and they contain no answer-specific information. Team decision, 2026-10-30. |
| 2 | Rubric and question text are ASCII (`N`, `n^3`, `<=`). | Unicode, as stored in the test set (`ℕ`, `n³`, `≤`). | The test set is not edited. This difference is part of what is measured, and should be reported as its own slice. |
| 3 | Training user messages are built by `ilab data generate`, then `tools/combine_sdg.py`. | `<context>`, a blank line, the output format (row 4), a blank line, `Student Answer:`, then the answer (`ANSWER_LAYOUT`). | **Provisional.** Inferred from the seed `question` fields and from `combine_sdg.fix_context`, but not yet compared with a real `skills_train_msgs` line. |
| 4 | No output-format instruction: the training answers teach the format. | An output-format block generated from each case's rubric: its IDs, names and maxima, with placeholders for the grades. It puts the Grade line last, while the training answers put it first. | The base model never saw the training answers. In the smoke test (job 1827184, v1) it gave sensible grades in its own format, and none could be parsed. With the Grade line first (v2), its Grade differed from its criterion sum in 3 of 12 development cases (job 1998799). Both models get the same block, and the parser reads the Grade line in either position. |

`grading_policies` is neither a grader-visible nor a held-out field in the dataset. Putting it in the prompt is a deliberate addition to question, rubric and answer, and it is recorded in every run config (`general_rules_source`).

## Keeping the prompt fixed

- `template_hash` covers everything about the prompt except the case itself:
  - the template version;
  - the system message and instruction;
  - the general rules;
  - `ANSWER_LAYOUT` and `LAYOUT_VERIFIED`;
  - the rendering code.
- Each case's messages also get their own hash (`prompt_sha256`).
- Every run saves the complete messages it sent (system and user) to its own `prompts.jsonl`, with each prompt's hash. Its `config.json` records the file's hash and the template hash.
- `compare.py` refuses to compare two runs unless:
  - their dataset hash, template hash, prompts-file hash and decoding settings are equal;
  - the saved messages are identical, case by case and system message included;
  - every saved reply was made from its saved prompt.

## Leak guard

Before a prompt is used, `check_no_leak` checks that no held-out text appears in it:

- `test_id`, `question_id`, `subtopic`, `parent_test_id`, `paraphrase_group`, `label_source`, `provenance`;
- the short question name the dataset's notes use (e.g. `nfa_16` for `csc236_B_nfa_16`);
- every draft justification.

Text that is also in the visible fields or the rules is allowed, because it reveals nothing. Six short draft justifications, such as "No correctness argument.", are word for word rubric expectations.

## Open points

- **Layout check (before any real run):** compare `ANSWER_LAYOUT` with one real `skills_train_msgs` line on Fir. If it differs, change `ANSWER_LAYOUT`, its test and table row 3 above, and give the template a new version. Then set `LAYOUT_VERIFIED = True`. Either change alters `template_hash`.
## Change log

- **2026-11-05: Group B dataset updated.** The dataset is now identified by SHA-256 `ecd69def58cf75b87032ef96419767e008e7481150170839411b47e8f1011cbc`. The file name and `version` field did not change, and no score or level changed. The template is still `eval-prompt-v3`, with the same `template_hash`.
  - **Q08 C2 rubric clarification.** In all three `csc236_B_struct_08` cases, `minimal` now covers an attempted concrete length calculation that is incorrect or doesn't use the induction hypothesis to justify the required form. `none` now covers giving no concrete calculation or relation for either recursive constructor. Rubric text is part of the prompt, so the prompts for these three cases changed, and runs made before this change can't be compared with later runs.
  - **Q08 C1 justification correction.** In `csc236_B_struct_08_ans02` and `csc236_B_struct_08_ans02_kw1`, the justification no longer says the property is mentioned only in the final conclusion, because the answer also mentions it in the inductive step. The actual issue is that the property isn't stated during proof setup. Justifications never reach the prompt.
  - **Human review.** All 60 cases now have `review_status` set to `human_reviewed`, and `provenance` records which cases began in the pilot. The labels are AI-drafted and human-reviewed, but remain provisional: they are not independently TA-verified or frozen, and the dataset's `status` still says it is not team-approved. The review metadata does not reach the prompt.
- **2026-11-02: `eval-prompt-v3`.** Moved the Grade line after the criterion lines and the `Total:` line, and added the rule that the Grade must equal the sum of all criterion points. Runs made with different template versions can't be compared with each other.
- **2026-11-02: `eval-prompt-v2`.** Added the output-format block. Runs made with v1 and v2 can't be compared with each other.
- **2026-10-30: `grading_policies[1]` shortened in the dataset.**
  - Before, the policy also named `asym_05`, `asym_12`, `nfa_16` and `dfa_15`, with team decisions about them. Every prompt therefore carried internal question names and exceptions meant for other questions.
  - It now states only the general principle: "…unless a criterion explicitly depends on earlier results."
  - The removed decisions are still part of the grading, because each one is written into that question's own rubric:
    - asym_05 and asym_12, C3: "each earned full or partial credit in C1/C2";
    - nfa_16, C1 and C3: "(correct subset construction of N)";
    - dfa_15, C3: "assessed separately under C2".
  - The prompt still uses all four policies exactly as stored in the dataset.
  - The file name and `version` field did not change. This changed the dataset's SHA-256 from the original v3 hash `ca2ef30d…c423` to `48a38706…a31c`.
  - The tests check that no prompt contains a question's short name. The three rubric phrases above were confirmed when the policy was shortened; the tests no longer check them.
