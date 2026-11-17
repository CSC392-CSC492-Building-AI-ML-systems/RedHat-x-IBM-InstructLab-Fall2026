#!/usr/bin/env python3
"""Merge a LoRA adapter into its base model and save a normal Hugging Face model folder.

Use this when vLLM can't apply the adapter at serve time (some layer types, such as
Qwen3.5/3.8's linear-attention projections, aren't supported as LoRA in every vLLM
version). The merged folder then goes in MODEL_PATH, with LORA_PATH left empty.

    python merge_lora.py --base <base model folder> --adapter <adapter folder> --out <new folder>

Run it with the Python environment you trained in (it needs torch, transformers and peft
versions that understand your model). Needs about 2x the model size in RAM.
"""
import argparse
import os
import shutil
import sys

import torch
import transformers
from peft import PeftModel
from transformers import AutoConfig

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

if os.path.exists(os.path.join(a.out, "config.json")):
    sys.exit(f"{a.out} already has a model in it; pick a new folder.")

cfg = AutoConfig.from_pretrained(a.base)
arch = (cfg.architectures or [""])[0]
cls = getattr(transformers, arch, None) or transformers.AutoModelForCausalLM
print(f"Loading base {a.base} as {cls.__name__} (bf16, on CPU)…", flush=True)
model = None
for kwargs in ({"dtype": torch.bfloat16}, {"torch_dtype": torch.bfloat16}):  # newer / older transformers
    try:
        model = cls.from_pretrained(a.base, **kwargs)
        break
    except TypeError:
        continue
if model is None:
    sys.exit("Could not load the base model with this transformers version.")

print(f"Applying adapter {a.adapter}…", flush=True)
peft_model = PeftModel.from_pretrained(model, a.adapter)

# A trained adapter has non-zero lora_B weights. All zeros means the adapter's weight names
# didn't line up with this model, so merging would silently give you the plain base model.
trained = [n for n, p in peft_model.named_parameters() if "lora_B" in n and p.detach().abs().sum() > 0]
total = [n for n, _ in peft_model.named_parameters() if "lora_B" in n]
print(f"{len(trained)} of {len(total)} LoRA layers carry trained weights", flush=True)
kinds = sorted({n.split(".lora_B")[0].rsplit(".", 1)[-1] for n in trained})
print("trained layer types:", ", ".join(kinds), flush=True)
if not trained:
    sys.exit("No trained LoRA weights were loaded: the adapter doesn't match this model's layer names. Nothing was saved.")

merged = peft_model.merge_and_unload()
os.makedirs(a.out, exist_ok=True)
print(f"Saving merged model to {a.out}…", flush=True)
merged.save_pretrained(a.out, safe_serialization=True, max_shard_size="5GB")

# Tokenizer, chat template and processor files come from the base model unchanged.
skip = {"config.json", "model.safetensors.index.json"}
for f in os.listdir(a.base):
    src = os.path.join(a.base, f)
    if os.path.isfile(src) and not f.endswith(".safetensors") and f not in skip and not os.path.exists(os.path.join(a.out, f)):
        shutil.copy2(src, a.out)
print("Done. Put this folder in MODEL_PATH and leave LORA_PATH empty.")
