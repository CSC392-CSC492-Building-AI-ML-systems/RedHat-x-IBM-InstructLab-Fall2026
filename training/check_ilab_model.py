"""Check whether InstructLab's trainer (instructlab-training 0.10.4) can take Qwen3.8-27B.

It runs on a login node with the existing ilab environment. It needs no GPU, installs
nothing and changes nothing. The model is built on the "meta" device, which has only
its shape and no weights, so it takes seconds and almost no memory.

It checks what the trainer itself checks before training:
1. which class AutoModelForCausalLM builds, since the trainer stops if the class name
   lacks "ForCausalLM",
2. that model.config.vocab_size exists, since the trainer reads it,
3. that the tokenizer has a chat template, since the trainer formats data with it,
4. which layers ilab's default LoRA targets (q_proj, k_proj, v_proj, o_proj) would hit,
   split into language layers and vision layers.

Run from the repo folder on Fir:
    module load python/3.11.5 && source env/ilab/.venv/bin/activate
    python training/check_ilab_model.py models/Qwen3.8-27B
"""
import sys
from collections import Counter

import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

path = sys.argv[1] if len(sys.argv) > 1 else "models/Qwen3.8-27B"

config = AutoConfig.from_pretrained(path)
print("Config class:", type(config).__name__, "| model_type:", config.model_type)

with torch.device("meta"):
    model = AutoModelForCausalLM.from_config(config, torch_dtype=torch.bfloat16)
name = type(model).__name__
print("AutoModelForCausalLM builds:", name)
print("1. Class name check:", "PASS" if "ForCausalLM" in name else "FAIL (the trainer stops here)")

vocab = getattr(model.config, "vocab_size", None)
print("2. model.config.vocab_size:", vocab if vocab is not None else "MISSING (the trainer would crash)")

tokenizer = AutoTokenizer.from_pretrained(path)
print("3. Chat template:", "PASS" if tokenizer.chat_template else "MISSING (the trainer stops here)")
if vocab is not None:
    print("   Tokenizer size", len(tokenizer), "vs vocab_size", vocab,
          "(the trainer resizes embeddings if the tokenizer is bigger)")

targets = ("q_proj", "k_proj", "v_proj", "o_proj")
hits = Counter()
for module_name, module in model.named_modules():
    if module_name.split(".")[-1] in targets and isinstance(module, torch.nn.Linear):
        part = "vision" if "visual" in module_name or "vision" in module_name else "language"
        hits[part] += 1
print("4. Default LoRA targets found:", dict(hits) or "NONE (the trainer stops here)")
print("   Language layers with full attention:",
      sum(1 for n, _ in model.named_modules() if n.endswith("self_attn")))

suffixes = Counter(n.split(".")[-1] for n, m in model.named_modules()
                   if isinstance(m, torch.nn.Linear) and "visual" not in n and "vision" not in n)
print("   All linear layer names in the language part:", dict(suffixes))
print("   _no_split_modules:", getattr(model, "_no_split_modules", None))
