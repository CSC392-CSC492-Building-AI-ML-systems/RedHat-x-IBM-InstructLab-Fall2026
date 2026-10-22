"""Fine-tune Qwen3.8-27B with LoRA, using Unsloth.

Run on a GPU node from the repo folder:
    python training/train_lora.py training/lora.yaml
For a quick test, --data, --output and --max-steps replace the file's
data and output folder and stop after a few steps.
"""
import argparse
import shutil
from pathlib import Path

import torch
import yaml
from unsloth import FastModel  # Unsloth has to be imported before trl
from unsloth.chat_templates import train_on_responses_only
from datasets import load_dataset
from trl import SFTConfig, SFTTrainer

parser = argparse.ArgumentParser()
parser.add_argument("settings")
parser.add_argument("--data")
parser.add_argument("--output")
parser.add_argument("--max-steps", type=int, default=-1)
args = parser.parse_args()

with open(args.settings) as f:
    cfg = yaml.safe_load(f)
data = args.data or cfg["data"]
out = Path(args.output or cfg["output"])

model, tokenizer = FastModel.from_pretrained(
    model_name=cfg["base_model"],
    max_seq_length=cfg["max_seq_length"],
    load_in_4bit=cfg["load_in_4bit"],
    full_finetuning=False,
)

# Qwen3.8 can also read images. We only train the language part.
model = FastModel.get_peft_model(
    model,
    finetune_vision_layers=False,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=cfg["lora_rank"],
    lora_alpha=cfg["lora_alpha"],
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=cfg["seed"],
)


# InstructLab writes each example as a list of chat messages. This turns
# each one into the exact text Qwen sees during a chat.
def to_text(example):
    return {"text": tokenizer.apply_chat_template(example["messages"], tokenize=False)}


dataset = load_dataset("json", data_files=data, split="train")
dataset = dataset.map(to_text, remove_columns=dataset.column_names)
print("First example as the model sees it:\n" + dataset[0]["text"])

trainer = SFTTrainer(
    model=model,
    processing_class=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        max_length=cfg["max_seq_length"],
        per_device_train_batch_size=cfg["batch_size"],
        gradient_accumulation_steps=cfg["gradient_accumulation_steps"],
        num_train_epochs=cfg["epochs"],
        max_steps=args.max_steps,
        learning_rate=cfg["learning_rate"],
        warmup_steps=10,
        optim="adamw_8bit",
        logging_steps=1,
        save_strategy="no",
        output_dir=str(out),
        report_to="none",
        seed=cfg["seed"],
    ),
)

# Learn from the answers only, not from the questions.
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|im_start|>user\n",
    response_part="<|im_start|>assistant\n",
)

trainer.train()
print(f"Peak GPU memory: {torch.cuda.max_memory_reserved() / 2**30:.1f} GiB")
model.save_pretrained(out)
tokenizer.save_pretrained(out)
# Keep the settings next to the adapter, so we always know how it was made.
shutil.copy(args.settings, out / "settings.yaml")
