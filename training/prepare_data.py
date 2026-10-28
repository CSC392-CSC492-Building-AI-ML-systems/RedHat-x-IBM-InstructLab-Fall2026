"""Clean InstructLab's generated data and write one training file.

For each example, this script
1. removes any thinking text (<think> ... </think>) from its messages,
2. drops the example if it
   - still has thinking that never finished,
   - has text from another model's chat format, like <|user|>,
   - is a knowledge answer that stops mid-sentence,
   - or is an exact copy of an example already kept,
3. keeps only the messages and writes the example to the output file.

Then it prints how many examples it kept and dropped, and why.
It never changes the input files, and it doesn't check whether answers are right.

Run from the repo folder:
    python training/prepare_data.py OUTPUT INPUT [INPUT ...]
INPUT is a knowledge_train_msgs or skills_train_msgs file from ilab or
tools/combine_sdg.py. With more than one INPUT, they are joined into one OUTPUT.
Add --tokenizer models/Qwen3.8-27B (in the training environment) to also
count how long the examples are in tokens.
"""
import argparse
import json
import re
from collections import Counter

# Text from other models' chat formats. If it shows up inside an example,
# the teacher kept writing past its answer.
LEAKS = ("<|user|>", "<|assistant|>", "<|system|>", "<|endoftext|>", "<|im_start|>", "<|im_end|>")
ENDINGS = tuple(".!?)]}$`\"'*")

parser = argparse.ArgumentParser()
parser.add_argument("output")
parser.add_argument("inputs", nargs="+")
parser.add_argument("--tokenizer")
args = parser.parse_args()


def problem(messages, dataset):
    """Say why an example should be dropped, or return None to keep it."""
    text = "".join(m["content"] for m in messages)
    if "<think>" in text or "</think>" in text:
        return "thinking that never finished"
    if any(leak in text for leak in LEAKS):
        return "leaked prompt text"
    answer = messages[-1]["content"].rstrip()
    # The teacher has a length limit per reply, and the last answer in a
    # reply sometimes stops mid-sentence when it runs out. Multiple choice
    # answers like "B) To define the output" often have no full stop, so
    # those are kept.
    multiple_choice = re.match(r"\(?[A-Da-d][).]\s", answer)
    if dataset.startswith("document_knowledge_qa") and not answer.endswith(ENDINGS) and not multiple_choice:
        return "answer cut off"
    return None


kept, seen, dropped, kinds = [], set(), Counter(), Counter()
for path in args.inputs:
    with open(path) as f:
        for line in f:
            example = json.loads(line)
            dataset = json.loads(example.get("metadata") or "{}").get("dataset", "")
            # The teacher sometimes writes out its thinking before the real
            # text. Removing it keeps only what it meant to write.
            messages = [
                {"role": m["role"], "content": re.sub(r"<think>.*?</think>\s*", "", m["content"], flags=re.S)}
                for m in example["messages"]
            ]
            reason = problem(messages, dataset)
            key = json.dumps(messages)
            if reason is None and key in seen:
                reason = "duplicate"
            if reason:
                dropped[reason] += 1
                continue
            seen.add(key)
            kinds[re.sub(r"_raft_p[\d.]+$", " (with extra notes)", dataset) or "unknown"] += 1
            kept.append({"messages": messages})

with open(args.output, "w") as f:
    for example in kept:
        f.write(json.dumps(example) + "\n")

print(f"Kept {len(kept)} examples, dropped {sum(dropped.values())}.")
for reason, n in dropped.most_common():
    print(f"  dropped, {reason}: {n}")
for kind, n in kinds.most_common():
    print(f"  kept, {kind}: {n}")

if args.tokenizer:
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    lengths = sorted(
        len(tokenizer.encode(tokenizer.apply_chat_template(e["messages"], tokenize=False), add_special_tokens=False))
        for e in kept
    )
    print(f"Length in tokens: median {lengths[len(lengths) // 2]}, longest {lengths[-1]}, total {sum(lengths):,}")
    for limit in (2048, 4096, 8192):
        over = sum(n > limit for n in lengths)
        print(f"  longer than {limit}: {over} ({over / len(lengths):.0%})")
