"""Ask the original model and a fine-tuned one the same questions, to compare their answers.

Run on a GPU node from the repo folder:
    python training/compare_adapter.py models/adapters/stage1_2026-10-28
It reads the questions from training/compare_questions.txt (--questions
picks another file), asks the original model first, then adds the trained
adapter and asks again. The answers are printed and also saved to
comparison.md in the adapter's folder.

This is a quick look, not a full evaluation. Most questions are about
topics in the training data, so a better answer can mean the model learned
the notes, or that it saw a very similar question during training.
"""
import argparse
from pathlib import Path

import yaml
from unsloth import FastModel  # Unsloth has to be imported before transformers and peft
from peft import PeftModel
from transformers import AutoTokenizer

# InstructLab puts this system message in every training example, so we use it here too.
SYSTEM = (
    "I am an advanced AI language model designed to assist you with a wide range of tasks "
    "and provide helpful, clear, and accurate responses. My primary role is to serve as a "
    "chat assistant, engaging in natural, conversational dialogue, answering questions, "
    "generating ideas, and offering support across various topics."
)

parser = argparse.ArgumentParser()
parser.add_argument("adapter")
parser.add_argument("--questions", default="training/compare_questions.txt")
parser.add_argument("--max-new-tokens", type=int, default=1024)
args = parser.parse_args()

adapter = Path(args.adapter)
# The settings saved with the adapter say which model it was trained on.
with open(adapter / "settings.yaml") as f:
    cfg = yaml.safe_load(f)
with open(args.questions) as f:
    questions = [line.strip() for line in f if line.strip() and not line.startswith("#")]

model, _ = FastModel.from_pretrained(
    model_name=cfg["base_model"],
    max_seq_length=cfg["max_seq_length"],
    load_in_4bit=cfg["load_in_4bit"],
)
tokenizer = AutoTokenizer.from_pretrained(cfg["base_model"])


def ask(question):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    # The training answers have no thinking, so thinking is off for both models.
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    # Always picking the most likely next token gives the same answer every run.
    output = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
    return tokenizer.decode(output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


print("First question as the model sees it:\n" + tokenizer.apply_chat_template(
    [{"role": "system", "content": SYSTEM}, {"role": "user", "content": questions[0]}],
    tokenize=False, add_generation_prompt=True, enable_thinking=False,
))

FastModel.for_inference(model)
original = [ask(q) for q in questions]

# Adding the adapter on top of the same model gives the trained version.
model = PeftModel.from_pretrained(model, str(adapter))
FastModel.for_inference(model)
trained = [ask(q) for q in questions]

lines = [f"# Original vs trained ({adapter.name})", ""]
for question, before, after in zip(questions, original, trained):
    lines += [f"## {question}", "", "**Original model:**", "", before, "", "**Trained model:**", "", after, ""]
text = "\n".join(lines)
print(text)
(adapter / "comparison.md").write_text(text)
