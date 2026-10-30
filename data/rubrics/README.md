# rubrics

The grading rubrics, one file per assignment question. Each rubric lists the criteria, the points for each, and what earns full, partial, minimal or no credit.

## This week's ownership

Ray leads the rubric work. This is a separate workstream from writing topic knowledge entries.

The rubric lead should:

- decide and document the rubric file format before adding question rubrics;
- create one rubric per selected assignment question, with criteria, points, and descriptions of full, partial, minimal, and no credit;
- coordinate with the test-set authors so each test answer is graded against the rubric for its question.

Ray also contributes to the ethics documents, with Sungmin (also called Ashton) leading that work. Josh and Nikita own multiple knowledge topics, while Daniel owns one topic alongside cluster and InstructLab setup; see [taxonomy/README.md](../taxonomy/README.md).

The model grades against these files, so once test answers have been written against a rubric, don't change it without updating and rechecking the affected test answers. Part of milestone 1.

## Rubric
rubric_induction_v1.json contains a minimal induction problem rubric for our usage.

Usage: The same induction rubric can be used in different types of problem examples. It is the job of the problem example to connect a specific class of problem (e.g. sum proof vs divisibility proof) to the abstracted induction proof structure. 

Note on YAML: Writing a vertical bar (|) before a multiline string tells YAML to treat it as a single multiline string. This allows the use of colons in a rubric. 

Note on grading output format: This should probably be checked.

## Training-seed rubrics (one YAML file per question)

The `*.yaml` files here are the source for the grading seeds in
`taxonomy/compositional_skills/grounded/grading/csc236/`. Each file holds one original question
(not taken from a term test) and its rubric, in the same shape as the test set
(`test_set/groupB_60_draft.json`): criteria `C1`..`Cn`, each with a `max` and four levels
(`full`, `partial`, `minimal`, `none`). Matching the test set means the model trains on the same
rubric format it is evaluated on.

| File | Folder | Total |
| --- | --- | --- |
| `psi_divisible_by_6.yaml` | `induction_simple` | 10 |
| `pci_sequence_closed_form.yaml` | `induction_complete` | 13 |
| `structural_prop_brackets.yaml` | `structural_induction` | 13 |
| `regex_no_double_zero.yaml` | `regex` | 10 |
| `recurrence_4T_half_n_squared.yaml` | `recurrences` | 10 |
| `asymptotic_smallest_c_cubic.yaml` | `asymptotic_analysis` | 10 |
| `dfa_contains_bb.yaml` | `dfa_nfa` | 10 |
| `loop_invariant_count_negatives.yaml` | `program_correctness` | 10 |

### File format

```yaml
id: psi_divisible_by_6
targets:
  - "**/grading/csc236/induction_simple/qna.yaml"   # which seed files use it
match: "6 divides n^3 + 11n"                         # text that identifies its seeds
question: |
  Let N = {0, 1, 2, ...}. Use simple induction on n to prove ...
criteria:
  - id: C1
    criterion: Predicate and base case
    max: 3
    levels:
      full:    {points: 3, expectation: "..."}
      partial: {points: 2, expectation: "..."}
      minimal: {points: 1, expectation: "..."}
      none:    {points: 0, expectation: "..."}
general_rules:
  - "..."
```

Rules for writing one:

- Every criterion has all four levels, `full` equals `max`, `none` is 0, and points strictly decrease.
- Put the specific facts a grader needs (base-case values, the correct constant, the reference
  automaton) inside the level expectations. There is no separate reference solution, because the
  test set gives the grader only the question, rubric and student answer.
- Write every special rule (required method, caps, "deduct each flaw once") in `general_rules`.
- Don't reuse term-test questions or any question in `test_set/`.

### Seed answer format

Each seed's answer gives one line per criterion, then the total:

```
**Grade:** 8 / 10

**Feedback:**
- C1 Predicate and base case: full (3/3). <one-sentence reason>
- C2 Induction hypothesis: full (3/3). <reason>
- C3 Inductive step: partial (2/4). <reason>
Total: 3 + 3 + 2 = 8.
```

### Commands (from the repository root)

```bash
pip install ruamel.yaml
python tools/rubrics.py stamp            # show which seed contexts differ from these files
python tools/rubrics.py stamp --write    # rebuild them (question + rubric)
python tools/rubrics.py validate         # check rubrics and seeds before data generation
```

`validate` fails if a seed's level or points don't match its rubric, if the criterion points don't
add up to the grade, or if a context has drifted from its rubric file. Edit the rubric here, never
inside `qna.yaml`.