# eval: the GradeAI Evaluation Suite

Runs the test set against the base model and the fine-tuned model with identical prompts and decoding settings, parses each criterion-level grade, scores it against the labels, and compares the two models. Part of milestone 7.

> **All results are provisional.** The Group B labels are drafts (v3): not human-verified and not frozen. Every output file says so.

## Use

On Fir, as one SLURM job (see the header of [`jobs/run_eval.sh`](jobs/run_eval.sh)):

```bash
ADAPTER=models/adapters/<name> bash eval/jobs/run_eval.sh --check     # login node, no GPU
ADAPTER=models/adapters/<name> sbatch eval/jobs/run_eval.sh            # base, fine-tuned, comparison
sbatch eval/jobs/run_eval.sh -- --test-type paraphrase,sensitivity     # options go to both runs
```

By hand, with a vLLM server already running:

```bash
python eval/run_eval.py --model base --out ~/scratch/gradeai-eval/runs --endpoint http://localhost:8000/v1
python eval/run_eval.py --model fine_tuned --adapter models/adapters/<name> --out ~/scratch/gradeai-eval/runs \
    --endpoint http://localhost:8000/v1
python eval/compare.py --base <base run> --fine-tuned <fine-tuned run> --out ~/scratch/gradeai-eval/compare
python eval/run_eval.py --rescore <run folder>      # re-score saved replies with the current code, no model
```

Filters: `--test-type`, `--topic`, `--question-id`. Output folders must be outside the repo, because they contain test-set text. If a run stops early (time limit, crash), start a new one: only runs with status `complete` can be compared or re-scored.

## Modules

| File | Does |
|---|---|
| `dataset.py` | Loads the test set and checks its SHA-256. Selects cases with filters, adding variant parents as context. |
| `prompt.py` | Builds the prompt (question, rubric, the 4 grading policies, output format, answer), with a leak guard and template hash. See [`PROMPT.md`](PROMPT.md). |
| `backends.py` | Sends prompts to vLLM: fixed decoding, no retries, failures recorded. |
| `parse.py` | Parses the Markdown grade. Failed predictions are never turned into 0. |
| `metrics.py` | All metrics, with paired-ready bootstrap intervals. |
| `run_eval.py` | One run: prompts, replies, parsed grades, metrics, `summary.md`. |
| `compare.py` | Base vs fine-tuned, after checking the runs are comparable. |
| `report.py` | Writes `summary.md`. |
| `jobs/` | SLURM job script and its preflight checks. |

Tests: `python3 -m unittest discover -s eval/tests -t .` (offline; no model or GPU).

## Metrics (Proposal and Ethics document)

| Requirement | Where |
|---|---|
| Criterion agreement with the answer key (target ≥ 80 %) | `criterion.strict_exact_agreement`; also valid-only and within one level |
| MAE; mean signed error (harsh vs lenient grading) | `criterion.mae_points`, `criterion.mean_signed_error_points`, `total.*` |
| QWK | `qwk.levels`, `qwk.points_max_3`, `qwk.points_max_4` |
| Consistency (paraphrases keep their grade, target ≥ 90 %) | `relations.paraphrase_groups` (per-criterion and total), `relations.identical_to_parent.paraphrase` |
| Fairness (typos and grammar not penalized) | `relations.identical_to_parent.fairness` |
| Sensitivity (a removed step or added error lowers the grade) | `relations.sensitivity.affected_and_total_drop`, `.any_total_drop` |
| Robustness (prompt injection, keyword stuffing) | `relations.robustness` (pass rate, grade raised above the parent's) |
| Output correctness (valid format, scores in range) | `format.*`, `criterion.coverage` |
| Per-topic and per-test-type analysis; by rubric level | `breakdowns.topic`, `.test_type`, `.gold_level`, `.review_status` |
| Uncertainty | `headline_ci`: bootstrap intervals over questions; compare.py adds paired intervals |

Two definitions are still open team decisions, so both variants are reported:
- consistency as identical per-criterion levels or as identical totals;
- sensitivity as a drop on the affected criterion plus the total, or as any drop in the total.

### Not yet implemented

**Confidence flagging (Proposal objective 3, Ethics document).** The plan:
- grade each submission five times;
- flag criteria whose grades disagree;
- report whether flagged grades are wrong at least 2× as often as unflagged ones, whether at most 20 % of submissions are flagged, how many wrong grades go unflagged, and the run-to-run disagreement.

This needs a team decision on how the five runs should differ, because evaluation decodes at temperature 0. It is listed under `not_yet_implemented` in every `metrics.json` and `compare.json`.

**Also outside this suite:**
- general-capability checks (MMLU, MT-Bench, run through `ilab model evaluate`);
- the TA-time study.

## Changes in the simplification (2026-10-30)

The suite was cut back to what the evaluation needs. Breaking changes against earlier drafts:

**Removed:**
- **Resume.** `run_eval.py --resume`, `RESUME=` in the job script, `eval/jobs/resume.py`, `job.json`, the results-folder lock, recovery of a cut-off reply, SIGTERM handling, and the `sessions` / `recoveries` / `resumed_at` config fields. A stopped run stays `running`; start a new one.
- **Replay.** `--backend replay`, `--replay-file` and `ReplayBackend`. `--rescore` remains for re-scoring saved replies.
- **The shared prompts file.** `--build-prompts`, `--prompts` and `prompts_manifest.json`. Each run saves its own complete prompts; `compare.py` checks that they are byte-identical (see `PROMPT.md`).
- **Metric variants:**
  - worst-case strict MAE and MAE as a fraction of the maximum;
  - label-anchored sensitivity, and the unaffected-criteria check;
  - identical totals for single variant pairs (paraphrase groups still report totals);
  - inflation measured against the label;
  - the answer-style breakdowns (writing style is covered by the fairness test type).
- **Comparison output.** The `differences` list, with a verdict for every metric, and its improved/regressed tables. `compare.json` keeps `headline`, the full `metrics` of both models, `paired_criterion_outcomes` and `warnings`.

**Changed:**
- **Headline metrics:** `identical_to_parent` (all variant types pooled) is replaced by `fairness_identical`. Paraphrase and robustness keep their own headline entries.
- **`config.json`:** `prompts_file` is now `{"sha256", "records"}`.
- **Report:** `summary.md` and `compare.md` gain a "Not yet implemented" section.

Unchanged: the remaining CLI options, the run-folder layout (`config.json`, `prompts.jsonl`, `raw_outputs.jsonl`, `parsed.jsonl`, `metrics.json`, `summary.md`), and the names of every retained metric.

**Prompt `eval-prompt-v2` (2026-11-02):** adds an explicit output-format block; see `PROMPT.md`. Runs made with v1 can't be compared with v2 runs.

**Prompt `eval-prompt-v3` (2026-11-02):** puts the Grade line last and states that it must equal the sum of the criterion points; see `PROMPT.md`. Runs made with v2 can't be compared with v3 runs by `compare.py`.
