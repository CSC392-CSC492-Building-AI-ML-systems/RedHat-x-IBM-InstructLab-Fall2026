# Using Fir

We run InstructLab and our model (Qwen3.8-27B) on Fir, an Alliance cluster with H100 GPUs. Everything is already installed in our team folder, so you don't need to install anything yourself.

## Logging in

```bash
ssh USERNAME@fir.alliancecan.ca
```

Type your Alliance password (nothing shows as you type), then approve the Duo push on your phone.

## The team folder

```
/project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026
```

This is a copy of our GitHub repo, plus the things too big for GitHub: the model (`models/`) and the two Python environments (`env/ilab/.venv` and `env/model/.venv`).

Don't edit or commit code here. Make changes on your laptop and push them to GitHub. To bring the latest changes onto Fir, run `git pull` in this folder.

## Chatting with Qwen

1. Get a GPU for 2 hours, and wait until it says "granted":

   ```bash
   salloc --account=def-engine14 --gpus=h100:1 --cpus-per-task=12 --mem=128G --time=2:00:00
   ```

2. Start Qwen in the background:

   ```bash
   cd /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026 && module load opencv/4.13 python/3.13 cuda/13.2 && source env/model/.venv/bin/activate
   ```

   ```bash
   vllm serve models/Qwen3.8-27B --served-model-name qwen3.8-27b --max-model-len 32768 --max-num-seqs 256 > ~/vllm.log 2>&1 &
   ```

3. Watch it load. It takes about 5 to 10 minutes. When you see `Application startup complete`, press Ctrl+C (Qwen keeps running):

   ```bash
   tail -f ~/vllm.log
   ```

4. Switch to the InstructLab environment:

   ```bash
   deactivate && module load python/3.11.5 && source env/ilab/.venv/bin/activate
   ```

5. The first time only, set up ilab:

   ```bash
   ilab config init --non-interactive --taxonomy-path /project/def-engine14/RedHat-x-IBM-InstructLab-Fall2026/taxonomy --taxonomy-base empty
   ```

6. Chat (type `/q` to quit):

   ```bash
   ilab model chat --endpoint-url http://localhost:8000/v1
   ```

7. When you're done, type `exit` to give the GPU back. The time keeps counting while the session is open.

## Tips

- **Losing your connection ends your GPU session.** To avoid that, start `tmux` before `salloc`. If you use Ghostty, start it with `TERM=xterm-256color tmux` instead.
- **To see your running jobs:** `squeue -u $USER`.
- **Rebuilding the environments** is only needed if one breaks: `sbatch env/setup_ilab.sh` and `bash env/setup_model.sh`, run from the team folder. Ask Daniel first.
