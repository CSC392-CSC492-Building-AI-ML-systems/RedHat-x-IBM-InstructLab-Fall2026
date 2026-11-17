# Group A test set (40 cases): final selection and validation report

**Version:** `final-v1-2026-11-16`
**Data file:** `test_set/groupA_40_final.json`
**SHA-256:** `226fb91602ed06d3192b495a4ab2085553e3ee41fa1745c3337de4f0dcab81cc`

> **Review status.** All 40 cases had an **AI-assisted mathematical review** (Claude, 2026-11-16) that covered every criterion. A **human** decided the flagged criteria of 4 cases. **No case has been independently verified end to end by a human.** The labels of the other 36 cases rest on the teacher-model generator plus the AI review.
>
> The file is final for this version, but it is **not frozen**. To freeze it, a human or the team signs off and records the SHA-256 above.

## 1. Files

| File | Role | SHA-256 |
|---|---|---|
| `test_set/groupA_40_final.json` | Final Group A set (this version) | `226fb916…ab81cc` |
| `test_set/groupA_40_final_report.md` | This report | — |
| `test_set/drafts/groupA_40_candidates.json` | Candidate draft v1, kept unchanged for traceability | `c0ec9dc0…185edc` |
| `test_set/drafts/groupA_selection_report.md` | Selection report for the draft, kept unchanged | `28c9bea8…fe7f` |
| Fir: `data/combined/grade_first_test/skills_train_msgs.jsonl` | Generated source (454 rows), not modified | `0eef6beb…dd17c` |

The final file follows the Group B schema, and its field names are the ones `eval/` reads:

- `draft_ground_truth`, `ta_score`, `ta_criteria`, `expected_flags`
- `parent_test_id`, `expected_relation_to_parent`
- `review_status`, `label_source`, `provenance`

Group A adds these fields:

| Field | Contents |
|---|---|
| `general_rules` | The grading rules for each case (grader-visible) |
| `final_response_markdown` | The labels rendered in the training reply format |
| `original_generated_label` | The generator's levels, scores, reasons and verbatim `raw_response` |
| `corrections` | Every change from the generated label, with history |
| `human_decisions` | Human decisions on flagged criteria |
| `audit_notes` | Review observations that did not change the label |
| `review_flags` | Flags raised at selection time |
| `generation_metadata` | Fields from the generator |
| `source` | The Fir row, the seed-context hash and the candidate draft |
| `selection_reason` | Why the case was selected |

## 2. Selection (summary)

The full procedure is in `test_set/drafts/groupA_selection_report.md`.

- **Source:** Raynard's grade_first_test generation on Fir, 2026-11-16: 454 candidates for 48 seed questions.
- **Excluded before selection:**
  - 12 answers that duplicate training answers;
  - 24 unconfirmed rows;
  - 18 near-duplicate flags;
  - 5 minimal pairs with training answers.
- **Set aside:** recurrences_03_a08, which has the same C1 rubric-order problem as recurrences_05_a05.
- **Eligible pool:** 419.
- **Selected:** 40 cases, 5 per topic (8 topics). Each case comes from a different seed question.
- **Mix:** all four levels, both maximum totals (31 cases out of 10, 9 out of 13), and 8 answers with embedded instructions.

## 3. Review methodology

### 3.1 AI-assisted review (Claude, 2026-11-16): all 40 cases, every criterion (129 criteria)

For each criterion, the reviewer worked out the level independently from the question, rubric, general rules and student answer. It then compared that level with the label and its justification. Facts that can be computed were computed:

| Topic | Computational check |
|---|---|
| asymptotic_analysis | For all 5 questions, computed the smallest c and its smallest n₀, which match the rubric (c = 7/3/5/6/4, n₀ = 3/7/9/6/6). Checked the students' constants, reductions and bounds. |
| dfa_nfa | Simulated the two complete student machines on all strings over {a, b} up to length 10. Checked the other three answers transition by transition against the rubric's DFA. |
| induction, program_correctness | Checked the claimed identities, divisibility facts and algebra steps symbolically and numerically. |
| recurrences | Checked all 5 closed forms against the recurrence for n = 2⁰…2²⁰ (3⁰…3¹²). Checked the general form in recurrences_05_a05 for every i. |
| regex | Compared every student expression with L on all strings up to length 10. |

**Limits**
- An AI review can be wrong.
- The numerical checks are finite, although every claim checked has a standard proof.
- Judgments such as whether T1 and T2 are "arbitrary" or a goal is "stated" are interpretive.

### 3.2 Human review (Sungmin, `chosun29`, 2026-11-16)

Working from the AI audit report, Sungmin:
- decided the flagged criteria of 4 cases (§4.1);
- asked for the justification fixes in 3 cases (§4.2).

No human re-graded any case end to end.

### 3.3 Status values in the file

| `review_status` | Cases | Meaning |
|---|---|---|
| `ai_reviewed` | 36 | Every criterion checked in the AI review. No human decision was needed. |
| `ai_reviewed_with_human_decisions` | 4 | As above, plus a human decided the criteria listed in `human_decisions`. |

| `provenance` | Cases |
|---|---|
| `generated_unchanged` | 33 |
| `generated_justification_revised` | 5 (asymptotic_analysis_03_a09, asymptotic_analysis_02_a07, regex_01_a03, recurrences_05_a05, regex_06_a08) |
| `generated_label_revised` | 2 (regex_04_a06, structural_induction_01_a07) |

## 4. Corrections

Each correction is recorded in its case's `corrections`, with from/to values, reason, evidence, proposer and approval. The generator's label and `raw_response` stay unchanged in `original_generated_label`.

### 4.1 Grading decisions

| Case | Criterion | Generated | Final | Total | Record |
|---|---|---|---|---|---|
| regex_04_a06 | C1 Soundness | partial (2/4) | **none (0/4)** | 4 → **1/10** | corr-03, dec-01 |
| | C2 Completeness | minimal (1/3) | **none (0/3)** | | v1-corr-01 (approved), dec-01 |
| | C3 Explanation | minimal (1/3) | minimal (1/3) | | — |
| recurrences_05_a05 | C1 Unrolling | minimal (1/4) | minimal (1/4), justification rewritten | 6/10 | corr-04, dec-02 |
| structural_induction_01_a07 | C2 Hypothesis | minimal (1/3) | **partial (2/3)** | 8 → **9/13** | corr-05, dec-03 |
| regex_06_a08 | C2 Completeness | minimal (1/3) | minimal (1/3), justification corrected | 2/10 | v1-corr-02 (approved), dec-04 |
| | C1 Soundness | minimal (1/4) | minimal (1/4), kept | | dec-04 |

**Mathematical basis**
- **regex_04_a06:** in `r = (000 + 111)*(0 + 1)`, the final `(0 + 1)` is mandatory, so every matched string has length 3m + 1. Up to length 10, r matches 30 strings, none of them in L, and misses all 585 strings of L.
- **regex_06_a08:** `(10 + 0)*` produces exactly the strings in which every 1 is immediately followed by 0. It matches 10 and 1010. Every string of L it misses ends with 1 or contains 11, and both kinds occur on their own (for example 1, 01 and 101; 110 and 0110).
- **recurrences_05_a05:** the general form 8ⁱT(n/2ⁱ) + n²(2ⁱ − 1) and the closed form 2n³ − n² are correct. Only one explicit substitution is shown, and the rubric's minimal level reads "Only one substitution".
- **structural_induction_01_a07:** the student wrote "We assume that the property holds for all smaller trees T1 and T2 in FBT" after defining P(T) in the first line. That names both subtrees, but it never writes P(T1) and P(T2) and never introduces T1 and T2 as arbitrary.

### 4.2 Justification fixes (levels unchanged)

| Case | Criterion | Problem in the generated reason | Fix |
|---|---|---|---|
| asymptotic_analysis_03_a09 | C2 | Called n(n − 3) ≥ 0 a "false inequality". It is true for every n ≥ 3. | The real defect: the constant 12 is dropped, so the student does not prove the required n(n − 3) ≥ 12. |
| asymptotic_analysis_02_a07 | C2 | The same problem with n²(n − 5) ≥ 0, which is true for every n ≥ 5. | The constant 20 is dropped, so the student does not prove the required n²(n − 5) ≥ 20. |
| regex_01_a03 | C1 | Cited the explanation, but general rule 1 grades the expression itself. | Now cites the fixed suffix 01 of r. |
| regex_01_a03 | C3 | Named only the missing empty-prefix remark. | The actual gap: the answer never shows that a string ending with 01 has the form x01 with x ∈ L((0 + 1)*). |

No justification fix contradicted its score.

In both asymptotic cases, the student's own bounds (18 and 36) would exceed the dropped constants (12 and 20). However, the answers never compare against them, and the rubric names a dropped constant as minimal. The levels were therefore kept, and this is recorded in `audit_notes`.

### 4.3 Effect

- **Criteria:** 3 of 129 changed level. Two were lowered (regex_04_a06 C1 partial → none, C2 minimal → none) and one was raised (structural_induction_01_a07 C2 minimal → partial).
- **Agreement:** generated vs final exact level agreement is 0.977 (126/129); QWK is 0.986.
- **Totals:** 2 cases changed (regex_04_a06: 4 → 1; structural_induction_01_a07: 8 → 9).
- **Justifications:** 9 rewritten.

## 5. Final distributions

### 5.1 Level counts

| | full | partial | minimal | none |
|---|---|---|---|---|
| Final | 59 | 14 | 18 | 38 |
| Generated | 59 | 14 | 20 | 36 |

### 5.2 Final levels by topic (full / partial / minimal / none)

| Topic | full | partial | minimal | none |
|---|---|---|---|---|
| asymptotic_analysis | 7 | 1 | 4 | 3 |
| dfa_nfa | 6 | 1 | 4 | 4 |
| induction_complete | 11 | 3 | 1 | 5 |
| induction_simple | 8 | 1 | 1 | 5 |
| program_correctness | 6 | 2 | 1 | 6 |
| recurrences | 7 | 2 | 1 | 5 |
| regex | 6 | 2 | 3 | 4 |
| structural_induction | 8 | 2 | 3 | 6 |

### 5.3 Total-score bands (share of the maximum)

| Band | 0 % | 1–39 % | 40–69 % | 70–99 % | 100 % |
|---|---|---|---|---|---|
| Final | 4 | 10 | 11 | 7 | 8 |
| Generated | 4 | 9 | 12 | 7 | 8 |

**Mean score:** 56.5 % of the maximum.

### 5.4 All 40 cases

Levels are in criterion order: F full, P partial, m minimal, 0 none.

**Cases out of 10**

| Case | Levels | Final | Status | Notes |
|---|---|---|---|---|
| asymptotic_analysis_06_a02 | FFF | 10 | ai | |
| asymptotic_analysis_05_a03 | mm0 | 2 | ai | |
| asymptotic_analysis_01_a05 | F00 | 3 | ai | |
| asymptotic_analysis_03_a09 | FmF | 7 | ai | justification fixed; embedded plea |
| asymptotic_analysis_02_a07 | FmP | 6 | ai | justification fixed; embedded TA claim |
| dfa_nfa_04_a01 | FFF | 10 | ai | |
| dfa_nfa_03_a03 | 000 | 0 | ai | metadata facts partly wrong |
| dfa_nfa_01_a04 | m0m | 2 | ai | |
| dfa_nfa_05_a06 | Fmm | 6 | ai | embedded grading note |
| dfa_nfa_06_a08 | PFF | 8 | ai | |
| induction_simple_01_a02 | FFF | 10 | ai | |
| induction_simple_03_a04 | 000 | 0 | ai | |
| induction_simple_04_a10 | mFF | 8 | ai | embedded rubric check (at start) |
| induction_simple_05_a08 | FPF | 9 | ai | |
| induction_simple_06_a03 | F00 | 3 | ai | |
| program_correctness_05_a01 | FFF | 10 | ai | |
| program_correctness_02_a03 | 000 | 0 | ai | |
| program_correctness_01_a07 | 0F0 | 4 | ai | embedded note to grader |
| program_correctness_06_a06 | PF0 | 6 | ai | |
| program_correctness_04_a06 | PFm | 7 | ai | |
| recurrences_06_a02 | FFF | 10 | ai | |
| recurrences_04_a03 | 00F | 3 | ai | |
| recurrences_02_a04 | 000 | 0 | ai | |
| recurrences_01_a08 | FFP | 9 | ai | |
| recurrences_05_a05 | mFP | 6 | ai + human | C1 justification rewritten |
| regex_02_a02 | FFF | 10 | ai | |
| regex_03_a10 | PF0 | 5 | ai | |
| regex_01_a03 | FFP | 9 | ai | C1/C3 justifications fixed |
| regex_04_a06 | 00m | **1** (was 4) | ai + human | C1, C2 → none |
| regex_06_a08 | mm0 | 2 | ai + human | C2 justification corrected; embedded note |

**Cases out of 13**

| Case | Levels | Final | Status | Notes |
|---|---|---|---|---|
| induction_complete_06_a01 | FFFF | 13 | ai | |
| induction_complete_05_a03 | F000 | 3 | ai | |
| induction_complete_03_a06 | 0FPF | 9 | ai | embedded SYSTEM text |
| induction_complete_04_a07 | FPF0 | 8 | ai | |
| induction_complete_01_a07 | PFFm | 9 | ai | |
| structural_induction_02_a02 | FFF | 10 out of 10 | ai | the only structural_induction case out of 10 |
| structural_induction_05_a03 | F000 | 3 | ai | |
| structural_induction_04_a05 | 00PF | 6 | ai | |
| structural_induction_01_a07 | FPFm | **9** (was 8) | ai + human | C2 → partial; embedded rubric check |
| structural_induction_03_a05 | mmF0 | 5 | ai | |

## 6. Validation (run 2026-11-16 on the file hash above)

3,569 automated checks ran, and **all passed**.

| Requirement | Result |
|---|---|
| Mathematical correctness of criterion levels | **Pass.** Every computational fact in §3.1 was recomputed for this validation, including the rubric's own c and n₀ statements. Examples: the regex results (regex_02_a02 and regex_01_a03 exact; regex_03_a10 has 10 extra strings, all of the form 1ᵏ0; regex_04_a06 matches 30 strings and misses all 585; regex_06_a08 has 221 extra and 364 missed), the 5 closed forms, and both DFA simulations. The interpretive judgments are as in the AI audit; see `audit_notes`. |
| Rubric levels, criterion scores and totals | **Pass.** Every level exists in the rubric and its points equal the score. The criteria sum to `total_score`, `max_score` equals the sum of the rubric maxima and the question's `[N marks]`, and `ta_score`/`ta_criteria` equal the labels. Each rubric runs full = max > partial > minimal > none = 0. |
| Labels vs justifications | **Pass.** Each justification was checked in the review. `final_response_markdown` parses with `eval/parse.py` (status ok, no warnings) back to exactly the levels, scores and justifications in `draft_ground_truth`. For the 33 unchanged cases it equals the generator's `raw_response` byte for byte. |
| No null scores or pending decisions | **Pass.** There is no null anywhere in `draft_ground_truth`, no correction in a pending state, no v1 pending keys, and every human decision names who made it. |
| No unintended changes to questions, rubrics, rules or answers | **Pass.** Question, rubric, general_rules and student_answer are equal to the candidate draft. The draft was byte-checked against Fir on 2026-11-16. Rendering question + rubric + general_rules with the training renderer reproduces the seed context byte for byte for all 40 cases (`source.prompt_context_sha256`). The draft files and Group B (`ecd69def…`) are unchanged. |
| Exactly the intended label changes | **Pass.** The differences from the generated labels are exactly the 9 criterion changes in §4, and each has a matching correction record whose from/to values agree with the labels. |
| No exact or near-duplicate overlap with training | **Pass** (details in §7). |
| No leakage into model-facing prompts | **Pass.** Each case's prompt was built as `eval/` would build it, with its own general_rules. None of the following appear in it unless the text is also part of the visible fields: ids, labels and justifications (generated and final), reply lines, label source, provenance, audit notes, review flags, generator facts or checks. `eval/prompt.check_no_leak` passes for all 40. No label text appears inside a student answer. |
| Structure | **Pass.** 40 unique test_ids; 5 cases in each of the 8 topics; 40 distinct seed questions. Every case has exactly the declared visible and held-out fields, and the two lists do not overlap. Every generated level equals the generator's target level. |

## 7. Training-set overlap

| Comparison | Result |
|---|---|
| Fir training answers (2026-11-16; `data/generated/stage2_v2clean_2026-11-15/train.jsonl`, 1,948 answers) | No exact or normalized duplicate. No answer reaches the near-duplicate threshold used at selection (token ratio ≥ 0.85 to its nearest same-seed training answer). Highest values among the 40: difflib 0.83 (induction_complete_01_a07), 10-gram containment 0.58 (dfa_nfa_06_a08), tf-idf cosine 0.96 (induction_simple_05_a08). Same-seed training pairs themselves reach difflib p99 0.90 and cosine p95 0.90. |
| Taxonomy seed answers in the repo (48) | No exact duplicate; highest token ratio 0.662. |
| Group B answers (60) | Highest token ratio 0.395. |
| Within the 40 | Highest token ratio 0.658 (two DFA answers in the same table format). |

Group A reuses the training questions and rubrics by design; only the answers are new.

The Fir comparison was run earlier on 2026-11-16, and the Fir session had expired by the time of this validation. **Repeat it if the training set changes**, for example after the pipeline update in commit `4a7bccb`.

## 8. Evaluation Suite compatibility

The labels, the reply format and the metrics work with `eval/` unchanged. Rendering the final labels as replies and passing them through `eval/parse.py` and `eval/metrics.py` (in memory, no model run) gives:
- strict exact agreement 1.0;
- MAE 0;
- QWK 1.0;
- format compliance 1.0.

`dataset.select` selects all 40.

Loading the file needs the integration changes below. The suite was built for Group B, which has dataset-wide `grading_policies`. **Group A carries the training seed's own rules in each case**, and those rules are part of what the labels assume (for example "grade C1 and C2 on the expression, not the explanation").

| # | Where | What fails now | Change needed |
|---|---|---|---|
| 1 | `eval/dataset.py:37`, `:109` | `load()` rejects `grader_visible_fields` = question, rubric, general_rules, student_answer | Accept this field list, and let `grader_input` return `general_rules` |
| 2 | `eval/prompt.py:119` | `build_user_message` requires exactly the three Group B fields | Allow `general_rules` |
| 3 | `eval/prompt.py:163–164`, `:193–195`, `:219` | `messages_for_case` reads `ds.grading_policies` → `KeyError` (Group A has no dataset-wide policies) | Use `case["general_rules"]` when present. Record "per-case rules" in `describe()`; `template_hash` cannot cover the rules, but each prompt's SHA-256 does. |
| 4 | `eval/dataset.py:38` | `check_structure` reports "test_id does not match the naming pattern" ×40 (its only finding) | Add a Group A pattern, for example `^csc236_A_[a-z_]+_[0-9]{2}_a[0-9]{2}$` |
| 5 | `eval/dataset.py:26`, `:32`; `eval/jobs/preflight.py:135`; `eval/prompt.py:211` | Defaults point to Group B | `run_eval.py` already takes `--dataset test_set/groupA_40_final.json --expected-sha256 226fb916…`. `preflight.py` and `python -m eval.prompt` call `dataset.load()` with the defaults and would need the same arguments. |
| 6 | `eval/metrics.py` (optional) | Robustness metrics need parent pairs; Group A's 8 embedded-instruction cases are standalone originals | Report them via a breakdown on `generation_metadata.embedded_instruction` (needs a metrics change), or compare those 8 cases separately |

Without changes 1–3 the suite **fails loudly** at load; it does not silently grade with the wrong rules.

One known prompt difference is unchanged: `eval/` appends an output-format block that training prompts did not have (documented in `eval/PROMPT.md`). It applies to Group A and Group B alike.

## 9. Remaining limitations

1. **No end-to-end human verification.** 36 labels are generator output confirmed only by the AI review.
2. **Interpretive borderlines** were kept as labelled and recorded in `audit_notes`:
   - regex_06_a08 C1 minimal: r restricts 1s, not 0s.
   - induction_complete_03_a06 C3 partial: k − 1 ≥ 1 is never derived.
   - recurrences_02_a04 C3 none: "roughly n · log n".
   - The two dropped-constant cases (asymptotic_analysis_03_a09, asymptotic_analysis_02_a07), where the students' bounds would have sufficed.
3. **Rubric-order inversion in recurrences C1.** One substitution with a correct general form scores 1, below two substitutions with no general form, which score 2. This was kept in recurrences_05_a05 by decision, and recurrences_03_a08 (not in this set) has the same issue. It is worth a rubric fix in the training seeds.
4. **Criterion-independence results the team should confirm:**
   - dfa_nfa_05_a06: C1 full although state A has no single-target transitions.
   - program_correctness_01_a07: C1 none although the bound check is right.
   - structural_induction_04_a05: circular hypothesis, yet C3 partial and C4 full.
   - structural_induction_03_a05: C3 full with a witness that was never introduced.
5. **Generation artifacts left in the answers.** These may hint at the omitted part:
   - structural_induction_04_a05 starts with "Next,";
   - program_correctness_06_a06 says "Now for the second part" with no first part.
6. **Metadata error.** The generator facts for dfa_nfa_03_a03 say the answer gives no start state, but it names s0. This is held out and has no effect on the label.
7. **Not a frozen set yet.** The training-overlap check should be repeated against the final training data, and a human/team sign-off should record the SHA-256.

**Correction to the earlier audit report:** induction_complete_04_a07 is not cut off mid-sentence. It ends with a complete sentence right after invoking P(k − 1) and P(k), and it has no computation, which is consistent with C4 none.
