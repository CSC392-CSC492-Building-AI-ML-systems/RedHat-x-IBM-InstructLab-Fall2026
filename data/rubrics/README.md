# rubrics

The grading rubrics, one file per question. Each rubric lists the criteria, the points for each,
and what earns full, partial, minimal or no credit. These files are the source for the grading
seeds in `taxonomy/compositional_skills/grounded/grading/csc236/`, and the model is trained to
grade against them.

## Ownership

Nikita leads the rubric work. The rubric lead:

- keeps the file format below and decides any change to it;
- writes or reviews every rubric, and checks the facts in it (correct constants, closed forms,
  reference automata);
- runs `python tools/rubrics.py validate` before any data generation;
- works with the test-set authors so that every test answer is graded against the rubric for its
  question.

Once test answers or generated data depend on a rubric, don't change it without updating and
rechecking what depends on it. Part of milestone 1. For the rest of the team's roles, see
[taxonomy/README.md](../../taxonomy/README.md).

## Files

48 rubrics, 6 per grading folder. Each one is an original question in the style of the term
tests (not taken from a term test or from `test_set/`).

| Folder | Rubric files | Total |
| --- | --- | --- |
| `asymptotic_analysis` | `asymptotic_smallest_c_cubic`, `asymptotic_smallest_c_cubic_b`, `asymptotic_smallest_c_cubic_c`, `asymptotic_smallest_c_quadratic_a`, `asymptotic_smallest_c_quadratic_b`, `asymptotic_smallest_c_quartic` | 10 |
| `dfa_nfa` | `dfa_contains_bb`, `dfa_contains_01`, `dfa_ends_with_b`, `dfa_even_length`, `dfa_odd_ones`, `dfa_starts_with_a` | 10 |
| `induction_complete` | `pci_sequence_closed_form`, `pci_sequence_two_pow_minus_1`, `pci_sequence_n_plus_1_two_pow_n`, `pci_sequence_all_even`, `pci_fibonacci_lower_bound`, `pci_sum_of_distinct_powers_of_2` | 13 |
| `induction_simple` | `psi_divisible_by_6`, `psi_divisible_4_pow_n_minus_1`, `psi_divisible_n5_minus_n`, `psi_sum_powers_of_2`, `psi_sum_i_times_i_plus_1`, `psi_two_pow_n_at_least_n_squared` | 10 |
| `program_correctness` | `loop_invariant_count_negatives`, `loop_invariant_sum_list`, `loop_invariant_max_value`, `loop_invariant_find`, `loop_invariant_power`, `loop_invariant_all_positive` | 10 |
| `recurrences` | `recurrence_4T_half_n_squared`, `recurrence_2T_half_n`, `recurrence_3T_third_n`, `recurrence_2T_half_n_squared`, `recurrence_8T_half_n_squared`, `recurrence_T_half_plus_1` | 10 |
| `regex` | `regex_no_double_zero`, `regex_even_zeros`, `regex_ends_01`, `regex_exactly_one_b`, `regex_length_multiple_3`, `regex_same_first_last` | 10 |
| `structural_induction` | `structural_prop_brackets`, `structural_fbt_leaves_internal`, `structural_fbt_leaves_height`, `structural_odd_elements`, `structural_balanced_even_length` (13 each), `structural_sum_closed_multiples_of_3` (10) | 13 or 10 |

All files end in `.yaml`. The rubrics use the same shape as the test set
(`test_set/groupB_60_draft.json`): criteria `C1`..`Cn`, each with a `max` and four levels
(`full`, `partial`, `minimal`, `none`). That way the model trains on the same rubric format it is
tested on.

## File format

```yaml
id: psi_divisible_by_6
targets:
  - "**/grading/csc236/induction_simple/qna.yaml"   # which seed file uses it
match: "6 divides n^3 + 11n"                         # text that identifies its seed
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

Several rubrics share one folder: they have the same `targets` and different `match` texts, and
the folder's `qna.yaml` has one seed per rubric. The `match` text must appear on one line of the
question. With the fixed-rubric pipeline (`tools/make_fixed_rubric_pipeline.py`), the seeds are
the only questions the generated data uses, so each folder needs 5–6 different questions.

The `|` before `question:` makes YAML keep the question as one multi-line string, so it can
contain colons and code. Line breaks in it are kept as written.

## Rules for writing a rubric

- Every criterion has all four levels; `full` equals `max`, `none` is 0, and the points strictly
  decrease.
- Put the facts a grader needs (base-case values, the correct constant, the reference automaton)
  in the level expectations. There is no separate reference solution, because the test set gives
  the grader only the question, the rubric and the student answer.
- Write every special rule (a required method, caps, "deduct each flaw once") in `general_rules`.
- Check every fact the rubric states, ideally with a short script (for regex rubrics,
  `tools/filter_skills.py` brute-forces the language; add new ones to `REGEX_LANGUAGES`).
- Don't reuse term-test questions or any question in `test_set/`.

## Seed answer format

Each seed's answer has one line per criterion, then the total:

```
**Grade:** 8 / 10

**Feedback:**
- C1 Predicate and base case: full (3/3). <one-sentence reason>
- C2 Induction hypothesis: full (3/3). <reason>
- C3 Inductive step: partial (2/4). <reason>
Total: 3 + 3 + 2 = 8.
```

Give a folder's seeds a spread of scores, from full marks down to 0–2, so the teacher model sees
flawed answers as well as correct ones.

## Commands (from the repository root)

```bash
pip install ruamel.yaml
python tools/rubrics.py stamp            # show which seed contexts differ from these files
python tools/rubrics.py stamp --write    # rebuild them (question + rubric)
python tools/rubrics.py validate         # check rubrics and seeds before data generation
```

`validate` fails if a seed's level or points don't match its rubric, if the criterion points don't
add up to the grade, or if a context has drifted from its rubric file. Edit a rubric here, never
inside `qna.yaml`, then run `stamp --write`.