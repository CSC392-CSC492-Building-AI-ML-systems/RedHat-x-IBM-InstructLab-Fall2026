# GradeAI

AI-assisted grading for CSC236. TAs upload student work, your **InstructLab fine-tuned model running on Fir** grades it against the course rubric, and the team reviews, approves and exports grades for Crowdmark.

```
 Browsers (profs, TAs) ──HTTPS──▶  GradeAI web server  ◀──HTTPS (outgoing only)──  Fir GPU job
                                   · site + API             · vLLM serving your checkpoint
                                   · SQLite + uploaded files· gradeai_worker.py pulls queued
                                   · grading queue            files, grades them, posts results
                                   · Tesseract OCR for scans
```

- Fir never accepts incoming connections. The worker inside your Slurm job pulls work over HTTPS (Fir compute nodes have full internet access), so you don't need SSH tunnels or open ports.
- When no Fir job is running, uploads wait as **Waiting for model** and grade automatically when the next job starts. Rubric import from PDF/Word also needs the model online.
- Student work stays on your web server and your Fir allocation. Nothing is sent to a third-party AI, and the fonts are bundled, so pages make no third-party requests.

## What's in here

| Path | What it is |
|---|---|
| `src/` | React + TypeScript frontend (the design from the Figma prototype) |
| `server/` | Node server: logins, role-enforced API, live updates, uploads, grading queue, OCR |
| `src/lib/grading.ts` | The grading prompt, JSON schema, score normalisation, roster matching, plagiarism check (shared by server and browser) |
| `deploy/fir/` | Everything for Fir: setup script, Slurm job, worker, env template |
| `Dockerfile`, `docker-compose.yml`, `deploy/Caddyfile` | Web server with automatic HTTPS |
| `deploy/gradeai.service` | systemd unit if you'd rather not use Docker |
| `scripts/mock-model.py` | Fake model for trying the app without Fir |

## 1. Run the web server

You need a Linux server with a public hostname: a department server, or an [Alliance Cloud](https://docs.alliancecan.ca/wiki/Cloud) VM (request one through the Rapid Access Service). Point DNS at it and open ports 80 and 443.

```bash
git clone <this repo> gradeai && cd gradeai
cp .env.example .env
openssl rand -hex 32            # paste into WORKER_TOKEN in .env
nano .env                       # PUBLIC_URL and GRADEAI_DOMAIN
docker compose up -d --build
```

Open `https://your-domain`. The first visit asks you to **create the administrator account**. It starts with the CSC236 settings and the two Assignment 2 rubrics from the prototype; edit or delete them as you like.

Invite the team from **Settings → Team**. GradeAI makes a one-time sign-in link (valid 7 days) for you to send; it doesn't send email.

## 2. Put your model on Fir

**a. Copy your checkpoint to project storage.** Use the Hugging Face-format folder (it has `config.json` and `*.safetensors`). After `ilab model train` it's usually `~/.local/share/instructlab/phased/phase2/checkpoints/hf_format/samples_XXXX/`.

```bash
# on fir.alliancecan.ca
mkdir -p ~/projects/def-yourpi/gradeai
cp -r <checkpoint folder> ~/projects/def-yourpi/gradeai/model
```

**b. Install vLLM and the job files once**, from the Alliance wheelhouse:

```bash
scp -r deploy/fir you@fir.alliancecan.ca:gradeai-setup
ssh you@fir.alliancecan.ca
cd gradeai-setup && bash setup-fir.sh
```

**c. Configure** `~/gradeai/gradeai.env`:
- `MODEL_PATH`: the folder from step a
- `GRADEAI_URL`: your web server
- `GRADEAI_WORKER_TOKEN`: the same value as `WORKER_TOKEN` on the server
- `MAX_MODEL_LEN`: your base model's context, e.g. 4096 for granite-7b-lab

Then set `--account=def-yourpi` and `--time` in `~/gradeai/gradeai-model.sbatch`.

**d. Start it:**

```bash
sbatch ~/gradeai/gradeai-model.sbatch
tail -f gradeai-model-<jobid>.out        # "vLLM is up" → GradeAI shows the model online
```

GradeAI's sidebar shows **Model online** with the job number and end time, and any waiting files start grading.

### Keeping the model available

- Fir jobs run from 1 hour to 7 days (`--time`). Ten minutes before the limit the worker stops taking new files, finishes what it has, and exits cleanly. Unfinished files go back to the queue.
- Set `RESUBMIT=1` in `gradeai.env` to queue the next job as each one starts, so the model returns as soon as the scheduler allows. Only do this during grading periods: it uses your group's GPU allocation.
- If grading is bursty, just `sbatch` the job when TAs upload a batch. Files wait safely in the meantime.
- One H100 grades many files at once (`WORKER_CONCURRENCY`, default 8). Fir also has MIG GPU slices; a 7–8B model fits on one if you want shorter queue waits.

## 3. Match your fine-tuning format

The model only behaves as trained if the request looks like its training data. Check these against your InstructLab `qna.yaml` / generated data:

| Setting | Where | Default |
|---|---|---|
| System prompt | **Settings → AI Grading Model** | "You are GradeAI, a careful teaching assistant for CSC236…" |
| Grading instructions + rubric layout | `buildGradingPrompt()` in `src/lib/grading.ts` | Rubric criteria and levels, then the submission in `<submission>` tags |
| Output format | `gradingSchema()` in `src/lib/grading.ts` | JSON with per-criterion `earned`, `note`, plus `summary`, `confidence`, `concerns` |
| Structured output | `JSON_MODE` in `gradeai.env` | `json_schema` (vLLM forces valid JSON); use `guided_json` for older vLLM, `none` to turn off |
| Max submission length | **Settings → AI Grading Model** | 16,000 characters. Longer files are cut and flagged for review |

The server tolerates replies wrapped in code fences or a sentence, clamps scores to each criterion's maximum, and flags missing criteria for review. Self-reported confidence from a small model is a rough signal. **Settings → Model Info → TA agreement** tracks how often TAs keep the model's score, which is the better measure.

## Roles

The server checks every action, whatever the browser shows.

| | TA | Professor | Admin |
|---|---|---|---|
| Upload & grade, approve/override, regrade | ✓ | ✓ | ✓ |
| Create/edit rubrics, course settings, Crowdmark export, delete submissions | | ✓ | ✓ |
| Invite people, change roles, reset passwords, danger zone | | | ✓ |

Admins can **Preview as** another role from the sidebar to see what TAs see.

## Data and backups

Everything lives in `DATA_DIR` (the `gradeai-data` Docker volume): `gradeai.db` (SQLite: users, rubrics, grades, queue, activity) and `files/` (original uploads). To back it up:

```bash
docker compose exec gradeai node -e "new (require('node:sqlite').DatabaseSync)('/data/gradeai.db').exec(\"VACUUM INTO '/data/backup.db'\")"
docker compose cp gradeai:/data ./gradeai-backup-$(date +%F)
```

**Settings → Danger Zone** deletes one assignment's grades, or all course data, for good.

## Local development

```bash
npm install
cp .env.example .env    # set WORKER_TOKEN=dev-token, PUBLIC_URL=http://localhost:8080
npm run build && npm start                       # http://localhost:8080
# try grading without Fir (fake grades):
python3 scripts/mock-model.py 8001 local-key &
GRADEAI_URL=http://localhost:8080 GRADEAI_WORKER_TOKEN=dev-token VLLM_URL=http://127.0.0.1:8001/v1 \
  VLLM_API_KEY=local-key MODEL_NAME=mock python3 deploy/fir/gradeai_worker.py
```

`npm run dev` serves the frontend with hot reload, proxying `/api` to `localhost:8080`. Requires Node 22.13+ (it uses the built-in `node:sqlite`). For scans you need `tesseract` and `pdftoppm`.

## Troubleshooting

| Symptom | Check |
|---|---|
| Model never shows online | `gradeai-model-<job>.out`: "server refused the worker" means the tokens differ; "cannot reach" means check `GRADEAI_URL` and that HTTPS works from Fir (`curl -I $GRADEAI_URL`) |
| Job ends early, "vLLM did not start" | `vllm-<job>.log`: usually `MAX_MODEL_LEN` above the model's limit, or a wrong `MODEL_PATH` |
| Files fail with "too long for the model's context window" | Lower **Max submission length** in Settings, or raise `MAX_MODEL_LEN` |
| "structured output refused" in the worker log | Older vLLM: set `JSON_MODE=guided_json` |
| Scans fail | Use the Docker image (it includes Tesseract) or install `tesseract-ocr poppler-utils` |
| Someone forgot their password | **Settings → Team → Reset password** gives you a new sign-in link to send them |

## Configuration reference

Web server (`.env`): `PUBLIC_URL`, `WORKER_TOKEN`, `GRADEAI_DOMAIN`, `PORT` (8080), `DATA_DIR` (./data), `MAX_UPLOAD_MB` (25), `SESSION_DAYS` (14), `WORKER_TIMEOUT_SEC` (90), `TASK_LEASE_SEC` (600), `TASK_MAX_ATTEMPTS` (3), `COOKIE_SECURE` (auto from PUBLIC_URL), `TRUST_PROXY` (true).

Fir (`~/gradeai/gradeai.env`): `MODEL_PATH`, `MODEL_NAME`, `MAX_MODEL_LEN`, `GRADEAI_URL`, `GRADEAI_WORKER_TOKEN`, `WORKER_CONCURRENCY`, `JSON_MODE`, `RESUBMIT`, `GPU_MEMORY_UTILIZATION`, `VLLM_EXTRA_ARGS`, `STOP_BEFORE_END_SEC`.
