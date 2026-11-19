# GradeAI

AI-assisted grading for CSC236. GradeAI runs on your computer at `http://localhost:8080`. You upload student work, your **fine-tuned model running on Fir** grades it against the course rubric, and you review, approve and export the grades for Crowdmark.

```
 Your computer                                              Fir
 ┌──────────────────────────────────────────┐              ┌──────────────────────────────┐
 │ browser ─▶ GradeAI (npm start)           │              │ Slurm job on one H100        │
 │            · website, rubrics, grades    │   SSH tunnel │ · vLLM serving               │
 │            · grading queue               │◀────────────▶│   models/merged-v2clean      │
 │ worker (npm run model:connect) ──────────┼──────────────┼─▶ random port + key per job  │
 └──────────────────────────────────────────┘              └──────────────────────────────┘
```

- `npm run model:connect` submits the model job on Fir if none is running, waits for it, opens an SSH tunnel to it, and starts the worker. The worker takes queued files from GradeAI, sends them through the tunnel to the model, and saves the grades.
- When the model isn't connected, uploads wait as **Waiting for model** and grade on their own once it connects. Importing a rubric from PDF/Word also needs the model connected.
- Student work stays on your computer and your Fir allocation. Nothing goes to a third-party AI. GradeAI only accepts connections from this computer.

## What's in here

| Path | What it is |
|---|---|
| `src/` | React + TypeScript frontend (the design from the Figma prototype) |
| `server/` | Node server: sign-in, API, live updates, uploads, grading queue, OCR |
| `src/lib/grading.ts` | The grading prompt, JSON schema, score normalisation, roster matching, plagiarism check |
| `scripts/fir.sh` | Runs the model on Fir from your computer (`npm run model:…`) |
| `scripts/gradeai_worker.py` | Worker that connects GradeAI to the model |
| `scripts/setup.mjs` | One-time setup of `.env` (`npm run setup`) |
| `deploy/fir/` | Goes on Fir: model job, its helper, LoRA merge, setup script |
| `scripts/mock-model.py` | Fake model for trying GradeAI without Fir |

## 1. Set up Fir (once)

**a. Copy the Fir files and check your vLLM environment.** From this folder on your computer:

```bash
rsync -a --delete deploy/fir/ <you>@fir.alliancecan.ca:gradeai-setup/
ssh <you>@fir.alliancecan.ca 'bash -l gradeai-setup/setup-fir.sh'
```

This puts `gradeai-serve.sbatch`, `fir-ctl.sh` and the merge files in `~/gradeai` on Fir, and creates `~/gradeai/gradeai.env`. That file is already set for your project: `models/merged-v2clean`, the `env/model/.venv` vLLM environment (with modules `opencv/4.13 python/3.13 cuda/13.2`), a 16,384-token context and `--language-model-only`. Edit it on Fir if anything changes. Run the same two commands again whenever you update GradeAI. (Use `rsync` as shown, not `scp -r`: when `gradeai-setup` already exists, `scp -r` puts the new files in `gradeai-setup/fir/` and leaves the old ones in place.)

**b. Merge the adapter into the base model.** vLLM's live LoRA support doesn't reliably cover the linear-attention layers your Qwen3.8 adapter trained, so GradeAI serves a merged copy instead. On Fir:

```bash
M=/project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026/models
sbatch ~/gradeai/merge-lora.sbatch $M/Qwen3.8-27B $M/adapters/stage2_v2clean_2026-11-15 $M/merged-v2clean
```

It uses `env/train/.venv` and prints how many LoRA layers carry trained weights. To merge another adapter, change the last two paths and point `MODEL_PATH` in `~/gradeai/gradeai.env` at the new folder.

The model job asks for one H100, 8 CPUs and 128 GB of memory on `def-engine14`. To change that, edit the top of `~/gradeai/gradeai-serve.sbatch`.

## 2. Set up your computer (once)

You need Node 22.13 or newer and Python 3 (macOS already has it). For scanned or photographed submissions, also install OCR: `brew install tesseract poppler`.

```bash
cd app/gradeai
npm install
npm run setup        # asks for your Alliance username, writes .env with a private worker token
npm run build
```

## 3. Grade

```bash
npm start                  # terminal 1: GradeAI at http://localhost:8080
npm run model:connect      # terminal 2: start the model on Fir and connect it. Leave it open.
```

The first time you open `http://localhost:8080`, GradeAI asks you to **create the administrator account**. It starts with the CSC236 settings and the two Assignment 2 rubrics from the prototype.

`npm run model:connect` signs in to Fir (approve the MFA prompt), offers to start a model job if none is running (`MODEL_HOURS` in `.env`, default 4 hours), and then waits:

1. **Waiting for a GPU.** Fir schedules the job. Shorter jobs usually start sooner.
2. **Loading.** vLLM reads the 52 GB model into the GPU, which takes a few minutes.
3. **Connected.** The sidebar shows **Model online** with the job number and end time, and waiting files start grading.

When you're done, press Ctrl-C in terminal 2, then free the GPU:

```bash
npm run model:stop
```

Other commands: `npm run model:status` (waiting, loading or ready), `npm run model:log` (the model job's log on Fir) and `npm run model:start -- 8` (submit an 8-hour job without connecting).

**If your laptop sleeps or the Wi-Fi changes**, the worker puts unfinished files back in the queue and pauses. `model:connect` notices, signs in to Fir again and resumes. When the job reaches its time limit, the worker stops taking new files 10 minutes early. Start another job with `npm run model:connect`.

Your Fir sign-in is reused for 12 hours, so the `model:` commands don't ask for MFA every time.

## Match your fine-tuning format

The model only behaves as trained if the request looks like its training data. Check these against your InstructLab generated data:

| Setting | Where | Default |
|---|---|---|
| System prompt | **Settings → AI Grading Model** | "You are GradeAI, a careful teaching assistant for CSC236…" |
| Grading instructions + rubric layout | `buildGradingPrompt()` in `src/lib/grading.ts` | Rubric criteria and levels, then the submission in `<submission>` tags |
| Output format | `gradingSchema()` in `src/lib/grading.ts` | JSON with per-criterion `earned`, `note`, plus `summary`, `confidence`, `concerns` |
| Structured output | `JSON_MODE` in `.env` | `json_schema` (vLLM forces valid JSON); `guided_json` for older vLLM, `none` to turn off |
| Thinking | `ENABLE_THINKING` in `.env` | `false`: Qwen answers with the JSON directly |
| Max submission length | **Settings → AI Grading Model** | 16,000 characters. Longer files are cut and flagged for review |

GradeAI tolerates replies wrapped in code fences or a sentence, clamps scores to each criterion's maximum, and flags missing criteria for review. **Settings → Model Info → TA agreement** tracks how often reviewers keep the model's score.

## Accounts and roles

GradeAI only opens on this computer, so everyone who uses it uses this computer. You can still make separate accounts (**Settings → Team** creates a one-time sign-in link) so that approvals are recorded under each person's name.

| | TA | Professor | Admin |
|---|---|---|---|
| Upload & grade, approve/override, regrade | ✓ | ✓ | ✓ |
| Create/edit rubrics, course settings, Crowdmark export, delete submissions | | ✓ | ✓ |
| Invite people, change roles, reset passwords, danger zone | | | ✓ |

## Data and backups

Everything is in the `data/` folder: `gradeai.db` (users, rubrics, grades, queue, activity) and `files/` (original uploads). To back it up, stop GradeAI and copy the folder:

```bash
cp -R data ~/gradeai-backup-$(date +%F)
```

`data/` and `.env` are in `.gitignore`. Keep them out of the repo, because they contain student work and your worker token.

**Settings → Danger Zone** deletes one assignment's grades, or all course data, for good.

## Try it without Fir

```bash
npm run mock-model                                  # terminal 2: a fake model that makes up grades
set -a; source .env; set +a                         # terminal 3:
GRADEAI_URL=http://127.0.0.1:8080 GRADEAI_WORKER_TOKEN=$WORKER_TOKEN \
  VLLM_URL=http://127.0.0.1:8001/v1 VLLM_API_KEY=local-key MODEL_NAME=mock python3 scripts/gradeai_worker.py
```

`npm run dev` serves the frontend with hot reload, proxying `/api` to `localhost:8080` (run `npm run dev:server` alongside it).

## Troubleshooting

| Symptom | Check |
|---|---|
| `model:connect` says "Couldn't ask Fir about the model job" | Run the Fir setup (step 1a). Check `FIR_USER` in `.env` |
| It waits for a GPU for a long time | Fir is busy. Shorter jobs start sooner: set `MODEL_HOURS=2` in `.env`. Files wait in GradeAI meanwhile |
| "The model job ended before it was ready" | `npm run model:log`. Usually `MODEL_PATH` is wrong or not merged yet, or `MAX_MODEL_LEN` is above the model's limit |
| "GradeAI refused the worker" | You ran `npm run setup` after starting GradeAI. Restart `npm start` |
| "Couldn't open the tunnel on port 18000" | Another program uses that port: set `MODEL_TUNNEL_PORT=18001` in `.env` |
| Merge fails with `FileNotFoundError` for `adapter_model.safetensors` | The adapter's files are readable only by their owner. They need to run `setfacl -R -m g:def-engine14:rX <adapter folder>` |
| The model replies with `!!!!` or nonsense | You're serving an unmerged adapter (`LORA_PATH`). Merge it (step 1b) |
| Files fail with "too long for the model's context window" | Lower **Max submission length** in Settings, or raise `MAX_MODEL_LEN` on Fir |
| "structured output refused" in the worker output | Older vLLM: set `JSON_MODE=guided_json` in `.env` |
| Scans fail | `brew install tesseract poppler`, then restart GradeAI |
| Someone forgot their password | **Settings → Team → Reset password** gives a new sign-in link |

## Configuration reference

This computer (`.env`): `FIR_USER`, `WORKER_TOKEN`, `FIR_HOST` (fir.alliancecan.ca), `PORT` (8080), `MODEL_HOURS` (4), `MODEL_TUNNEL_PORT` (18000), `WORKER_CONCURRENCY` (8), `JSON_MODE` (json_schema), `ENABLE_THINKING` (false), `DATA_DIR` (./data), `MAX_UPLOAD_MB` (25), `SESSION_DAYS` (14), `WORKER_TIMEOUT_SEC` (90), `TASK_LEASE_SEC` (600), `TASK_MAX_ATTEMPTS` (3).

Fir (`~/gradeai/gradeai.env`): `MODEL_PATH`, `LORA_PATH`, `VLLM_VENV`, `MODULES`, `MODEL_NAME`, `MAX_MODEL_LEN`, `GPU_MEMORY_UTILIZATION`, `VLLM_EXTRA_ARGS`.
