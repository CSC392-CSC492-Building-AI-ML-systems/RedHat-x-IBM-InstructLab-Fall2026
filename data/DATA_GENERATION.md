# Generating synthetic data on Fir

How to run `ilab data generate` on Fir with our Qwen model as the teacher. Read [`fir-guide.md`](fir-guide.md) first for logging in and the team folder.

How it works: Qwen runs on a GPU as a server (vLLM), and ilab sends its generation requests to that server. ilab itself runs in the CPU-only `env/ilab` environment.

Tested on 2026-10-22 with ilab 0.26.1, instructlab-sdg 0.8.3, docling 2.138.0 and vLLM 0.25.0, on the `program_correctness` entry.

## One-time setup (each person, once)

instructlab-sdg 0.8.3 tries to download docling's models with a function that our docling version no longer has, and generation fails with `type object 'StandardPdfPipeline' has no attribute 'download_models_hf'`. To avoid that, download the models yourself and tell sdg where they are. sdg checks `~/.local/share/instructlab/sdg/models/config.yaml` first and skips its own download if the file exists.

On a login node:

```bash
cd /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026
module load python/3.11.5
source env/ilab/.venv/bin/activate

python -c "from pathlib import Path; from docling.utils.model_downloader import download_models; print(download_models(output_dir=Path.home() / 'scratch' / 'docling-models', progress=True))"

mkdir -p ~/.local/share/instructlab/sdg/models
cat > ~/.local/share/instructlab/sdg/models/config.yaml <<EOF
models:
  - path: $HOME/scratch/docling-models
EOF
cat ~/.local/share/instructlab/sdg/models/config.yaml   # should show a full path
```

Do **not** fix this by changing docling's version in the shared environment. Older docling needs an older `huggingface_hub`, which breaks other packages (`cannot import name 'BucketNotFoundError'`).

## Before each run: check your taxonomy entry

ilab downloads your source markdown from GitHub, at the commit in your `qna.yaml`. So:

1. The markdown is in `data/sources/csc236/<topic>/`, **not** in the taxonomy folder. Taxonomy leaf folders hold only `qna.yaml` and `attribution.txt`.
2. The folder name matches your `patterns:` line exactly. A typo (e.g. `program_correctnes`) gives `Failed to load document content`.
3. The commit is **pushed**, and `commit:` is the full 40-character SHA of a commit that contains the markdown. Check with:
   ```bash
   git ls-tree -r <SHA> --name-only | grep <topic>
   ```
4. No trailing spaces in `qna.yaml` (ilab's linter rejects them). Turn on "trim trailing whitespace" in your editor, or run `sed -i 's/[[:space:]]*$//' qna.yaml`.
5. On Fir, `git pull` in the team folder.

To test one entry without the others (which may be unfinished), copy it into its own taxonomy folder:

```bash
TOPIC=program_correctness
rm -rf ~/scratch/taxo-test
mkdir -p ~/scratch/taxo-test/knowledge/computer_science/csc236
cp -r taxonomy/knowledge/computer_science/csc236/$TOPIC ~/scratch/taxo-test/knowledge/computer_science/csc236/
```

## Running it

### 1. Get a GPU

Start `tmux` first, so a dropped connection doesn't end the session (`tmux attach` to get back).

```bash
tmux
salloc --account=def-engine14 --gpus=h100:1 --cpus-per-task=12 --mem=128G --time=2:00:00
```

Wait for `Nodes ... are ready`, then check the GPU:

```bash
nvidia-smi
```

It should show an H100 with a temperature (e.g. `25C`), power (e.g. `66W / 700W`) and about `0MiB` used. If it shows `ERR!`, the node is faulty: `exit` and ask again with `--exclude=<node name>`. The `NVML: Failed to get Compute running process count` lines after `salloc` are harmless.

### 2. Start Qwen

```bash
cd /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026 && module load opencv/4.13 python/3.13 cuda/13.2 && source env/model/.venv/bin/activate
```

```bash
vllm serve models/Qwen3.8-27B --served-model-name qwen3.8-27b /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026/models/Qwen3.8-27B --max-model-len 32768 --max-num-seqs 256 > ~/vllm.log 2>&1 &
```

The second name (the full model path) is required. ilab uses the `--model` value both as a folder to load the tokenizer from and as the model name it sends to vLLM, so vLLM must answer to the full path.

Wait until it's ready. The first start can take 15–20 minutes (it compiles GPU code). Later starts are faster because the result is cached in `~/.cache/vllm`. To watch it load:

```bash
tail -f ~/vllm.log
```

`tail -f` shows the end of the log and keeps printing new lines as vLLM writes them. When you see `Application startup complete`, press **Ctrl+C**. This only stops `tail`; vLLM keeps running in the background because of the `&` at the end of the `vllm serve` command. For a quick look without following, use `tail -n 30 ~/vllm.log` (the last 30 lines).

To confirm it's ready:

```bash
curl -s http://localhost:8000/v1/models
```

It's ready when this prints JSON listing both names. "Connection refused" means it's still loading. Start vLLM **only once**: if it's already running, a second copy can't fit on the GPU and its messages will mess up `~/vllm.log`. Check with `ps -u $USER -o pid,etime,cmd | grep "vllm serve" | grep -v grep`.

### 3. Switch to ilab

```bash
deactivate && module load python/3.11.5 && source env/ilab/.venv/bin/activate
ilab config init --non-interactive --taxonomy-path /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026/taxonomy --taxonomy-base empty   # first time only
```

### 4. Validate

```bash
ilab taxonomy diff --taxonomy-path ~/scratch/taxo-test --taxonomy-base empty
```

If it fails, the useful line is above the traceback:

```bash
ilab taxonomy diff --taxonomy-path ~/scratch/taxo-test --taxonomy-base empty 2>&1 | grep -E "ERROR|WARNING"
```

### 5. Generate

Keep the command on one line. A `\` at the end of a line only continues the command if nothing (not even a space) follows it.

```bash
ilab data generate --endpoint-url http://localhost:8000/v1 --model /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026/models/Qwen3.8-27B --taxonomy-path ~/scratch/taxo-test --taxonomy-base empty --sdg-scale-factor 5 --output-dir ~/scratch/sdg-test
```

Expected messages that are fine:

- `Found the docling models` (the one-time setup worked)
- `Tesseract not found` / `Failed to load Tesseract and EasyOCR` (OCR is only for scanned PDFs; our sources are markdown)
- `HF_HUB_ENABLE_HF_TRANSFER ... deprecated`

A small test (one topic, scale factor 5) takes roughly 30 minutes to a couple of hours. Check progress with:

```bash
tail -n 5 $(ls -t ~/.local/share/instructlab/logs/generation/*.log | head -1)
nvidia-smi    # GPU-Util above 0% means Qwen is working
```

## Time limits and resuming

**Checking your time.** From any terminal on Fir:

```bash
squeue -u $USER
```

The `TIME_LEFT` column shows how long your session has left (e.g. `1:23:10`). You can't extend a running session yourself, so if a run won't finish in time, let it reach a checkpoint and resume in a new session.

**What happens when time runs out.** Slurm ends the session: vLLM and `ilab data generate` are killed, the GPU is released, and you're dropped back on the login node (you'll see `CANCELLED ... DUE TO TIME LIMIT`). Files already written stay on disk, including the checkpoints.

**Resuming.** ilab saves checkpoints in `<output-dir>/checkpoints/` as batches finish. To continue:

1. Get a new GPU session (step 1) and start Qwen again (step 2).
2. Switch to ilab (step 3).
3. Rerun the **exact same** `ilab data generate` command, with the same `--taxonomy-path` and `--output-dir`.

The log should say it found existing checkpoints instead of `No existing checkpoints found ... generating from scratch`. Work that was in progress when the session ended is redone, but finished batches are kept. Don't change your `qna.yaml` between the interrupted run and the resumed one, or the checkpoints won't match the new seeds. If you did change it, delete `<output-dir>/checkpoints/` and start fresh.

For long runs (e.g. all topics), use a batch job (`sbatch`) with a longer `--time` instead of an interactive session.

### 6. Finish

Output is in `~/scratch/sdg-test/<timestamp>/`. Copy anything worth keeping to the team folder, since scratch is purged of old files. Then release the GPU:

```bash
pkill -f "vllm serve"
exit
```

Type `exit` when you're done with a GPU session, before starting another. Running `salloc` inside an existing session nests them, and when the outer one hits its time limit, both end.

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `trailing spaces (trailing-spaces)` | Spaces at the end of lines in `qna.yaml` | Remove them (see above) |
| `Failed to load document content` | Wrong folder name, pattern, or commit SHA, or the commit isn't pushed | Check with `git ls-tree -r <SHA> --name-only` |
| `StandardPdfPipeline has no attribute 'download_models_hf'` | One-time docling setup not done | Do the one-time setup |
| `Failed to load tokenizer ... at qwen3.8-27b` | `--model` was the short name | Pass the full model folder path |
| `404 ... model ... does not exist` | vLLM doesn't answer to the full path | Restart vLLM with both `--served-model-name` values |
| vLLM: `Failed to infer device type` | vLLM started on a node without a GPU | Run it inside `salloc`; check `hostname` and `nvidia-smi` |
| `nvidia-smi` shows `ERR!` | Faulty node | `exit`, then `salloc ... --exclude=<node>`, and report the node to support@tech.alliancecan.ca |
| vLLM log stuck after `torch.compile took ...` | First-time GPU kernel compile | Wait; or restart with `--gdn-prefill-backend triton` |
| `Got unexpected extra arguments` | Spaces after a `\` in a multi-line command | Put the command on one line |
