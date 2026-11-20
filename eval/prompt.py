"""Build the evaluation prompt: the same messages for the base and the fine-tuned model.

The rubric rendering below is copied from tools/rubrics.py (INSTRUCTION, LEVELS, WRAP, norm, fmt,
wrap, render_block, render_context), so that eval/ does not depend on that file.
eval/tests/test_prompt.py pins the text this copy produces, but does not compare it with that file.
The differences from the training prompt are deliberate, and eval/PROMPT.md lists them.

Only question, rubric and student_answer from a case reach the prompt, plus the general rules:
Group B's dataset-level grading_policies, or a Group A case's own general_rules (eval/dataset.py).
The student answer is used verbatim, never cleaned up: some answers contain errors, injection text or
fake grades on purpose.

eval-prompt-v3 is the default. eval-prompt-train-v1 (chosen with run_eval.py --template) is an optional,
diagnostic template with the layout the stage-2 adapter was trained on; see eval/PROMPT.md.

To print the exact prompt for one case (the group follows from the test_id):
    python -m eval.prompt csc236_B_cind_01_ans01
    python -m eval.prompt csc236_A_regex_04_a06
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import textwrap

from eval import dataset

# ---------------------------------------------------------------- copied from tools/rubrics.py

LEVELS = ["full", "partial", "minimal", "none"]
WRAP = 94

INSTRUCTION = ("Grade the student answer against the question and rubric below. For each criterion,\n"
               "choose the level that fits the answer and give a one-sentence reason.")


def norm(text) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def fmt(n: float) -> str:
    return f"{float(n):g}"


def wrap(text: str, first: str, rest: str) -> list[str]:
    return textwrap.wrap(norm(text), width=WRAP, initial_indent=first, subsequent_indent=rest,
                         break_on_hyphens=False, break_long_words=False)


def render_block(r: dict) -> str:
    total = sum(float(c["max"]) for c in r["criteria"])
    lines = [f"Rubric (Total {fmt(total)} pts):"]
    for c in r["criteria"]:
        lines.append(f"- {c['id']} {norm(c['criterion'])}: {fmt(c['max'])} pts.")
        for level in LEVELS:
            spec = c["levels"][level]
            lines += wrap(f"{level} ({fmt(spec['points'])}): {spec['expectation']}", "  ", "    ")
    rules = r.get("general_rules") or []
    if rules:
        lines.append("General rules:")
        for n, rule in enumerate(rules, 1):
            lines += wrap(f"{n}. {rule}", "", "   ")
    return "\n".join(lines) + "\n"


def render_context(r: dict) -> str:
    question = "\n".join(line.rstrip() for line in str(r["question"]).strip("\n").splitlines())
    return f"{INSTRUCTION}\n\nQuestion:\n{question}\n\n{render_block(r)}"


# ---------------------------------------------------------------- evaluation prompt

TEMPLATE_VERSION = "eval-prompt-v3"

# The system message in every InstructLab training example, as in training/compare_adapter.py.
SYSTEM = (
    "I am an advanced AI language model designed to assist you with a wide range of tasks "
    "and provide helpful, clear, and accurate responses. My primary role is to serve as a "
    "chat assistant, engaging in natural, conversational dialogue, answering questions, "
    "generating ideas, and offering support across various topics."
)

ANSWER_LABEL = "Student Answer:"
# Provisional. Inferred from the seed `question` fields, which start with "Student Answer:\n", and
# from tools/combine_sdg.py's fix_context, which leaves the context first and the submission after
# it. Check against a real skills_train_msgs line on Fir before any real evaluation run, then set
# LAYOUT_VERIFIED.
ANSWER_LAYOUT = "{context}\n{output_format}\n\n" + ANSWER_LABEL + "\n{student_answer}"
LAYOUT_VERIFIED = False

# Optional diagnostic template: the stage2_v2clean_2026-11-15 training layout, checked on Fir 2026-11-20.
# Training rendered every example without enable_thinking, so the chat template put REASONING_PREAMBLE
# and a blank line before the system message; evaluation runs with enable_thinking=False, where the
# chat template leaves it out, so this template puts it in the system message itself. The user message
# is the context, a blank line, "Student Answer:" and the answer, with no output-format block. Nothing
# asks for a reply order (the training replies put the Grade line first; parse.py reads either order).
TRAIN_TEMPLATE_VERSION = "eval-prompt-train-v1"
TEMPLATES = (TEMPLATE_VERSION, TRAIN_TEMPLATE_VERSION)
REASONING_PREAMBLE = ("Reasoning effort is set to xhigh. Please think carefully through the task, validate key "
                      "assumptions, consider plausible alternatives, and prioritize correctness, consistency, "
                      "and clarity in the final answer.")
TRAIN_SYSTEM = REASONING_PREAMBLE + "\n\n" + SYSTEM
TRAIN_ANSWER_LAYOUT = "{context}\n\n" + ANSWER_LABEL + "\n{student_answer}"

# Held-out fields whose text must never appear in a prompt, whatever its length. topic, test_type,
# group and review_status are left out: they are common words ("recurrences") that can appear in a
# rubric or in the grading rules without anything leaking.
LEAK_FIELDS = ("test_id", "question_id", "subtopic", "parent_test_id", "paraphrase_group",
               "label_source", "provenance", "seed_id")
# Besides those, every text of at least this many characters anywhere in a held-out field (labels,
# justifications, the generated reply, correction history, review notes, generation metadata) is
# checked. Shorter texts are mostly level names and common words.
LEAK_MIN_CHARS = 20
# The fields of a case the model may see (Group A also shows general_rules). Everything else is held out.
VISIBLE_FIELDS = ("question", "rubric", "general_rules", "student_answer")


class PromptError(Exception):
    pass


class LeakError(PromptError):
    pass


def render_output_format(rubric: list[dict]) -> str:
    """The reply format parse.py reads, with one line per criterion of this rubric. It uses only the
    rubric's ids, names and maxima; placeholders stand where the grades go."""
    total = fmt(sum(float(c["max"]) for c in rubric))
    lines = ["Write your grade in exactly this format, with exactly these criterion lines, and nothing else:", "",
             "**Feedback:**"]
    lines += [f"- {c['id']} {norm(c['criterion'])}: <level> (<points>/{fmt(c['max'])}). <one-sentence reason>"
              for c in rubric]
    lines.append("Total: " + " + ".join(f"<{c['id']} points>" for c in rubric) + " = <total points>.")
    lines += ["", f"**Grade:** <total points> / {total}", "",
              "<level> is full, partial, minimal or none, and <points> is what the rubric gives that level. "
              "The Grade must equal the sum of all criterion points."]
    return "\n".join(lines)


def build_user_message(grader_fields: dict, general_rules: list[str], template: str = TEMPLATE_VERSION) -> str:
    if set(grader_fields) != set(dataset.GRADER_VISIBLE):
        raise PromptError(f"the prompt takes exactly {list(dataset.GRADER_VISIBLE)}, "
                          f"got {sorted(grader_fields)}")
    context = render_context({"question": grader_fields["question"],
                              "criteria": grader_fields["rubric"],
                              "general_rules": general_rules})
    if template == TRAIN_TEMPLATE_VERSION:
        return TRAIN_ANSWER_LAYOUT.format(context=context, student_answer=grader_fields["student_answer"])
    return ANSWER_LAYOUT.format(context=context, output_format=render_output_format(grader_fields["rubric"]),
                                student_answer=grader_fields["student_answer"])


def build_messages(grader_fields: dict, general_rules: list[str], template: str = TEMPLATE_VERSION) -> list[dict]:
    """The chat messages sent to either model. Nothing here depends on which model is graded."""
    if template not in TEMPLATES:
        raise PromptError(f"unknown prompt template {template!r}; choose from {list(TEMPLATES)}")
    system = TRAIN_SYSTEM if template == TRAIN_TEMPLATE_VERSION else SYSTEM
    return [{"role": "system", "content": system},
            {"role": "user", "content": build_user_message(grader_fields, general_rules, template)}]


def short_question_id(question_id: str) -> str:
    """The name the dataset's notes use for a question: csc236_B_nfa_16 -> nfa_16,
    csc236_A_regex_04 -> regex_04."""
    return re.sub(r"^csc236_[AB]_", "", question_id)


def _texts(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _texts(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _texts(v)


def held_out_strings(case: dict) -> list[str]:
    found = [case[f] for f in LEAK_FIELDS if isinstance(case.get(f), str) and case[f]]
    found.append(short_question_id(case["question_id"]))
    found += [g["justification"] for g in case["draft_ground_truth"]["criteria"] if g.get("justification")]
    for field, value in case.items():
        if field not in VISIBLE_FIELDS:
            found += [s for s in _texts(value) if len(s.strip()) >= LEAK_MIN_CHARS]
    return list(dict.fromkeys(found))


def check_no_leak(messages: list[dict], case: dict, general_rules: list[str]) -> None:
    """Raise if held-out text reaches the prompt by any route other than the visible fields.

    Some held-out text is also visible on purpose: a short draft justification such as "No
    correctness argument." can be word for word a rubric expectation. Text that is already in the
    question, rubric, student answer or rules reveals nothing, so it is not counted.
    """
    text = "\n".join(m["content"] for m in messages)
    visible = json.dumps(dataset.grader_input(case), ensure_ascii=False) + "\n".join(general_rules)
    visible += "\n" + case["question"] + "\n" + case["student_answer"]
    for s in held_out_strings(case):
        if s in text and s not in visible:
            raise LeakError(f"{case['test_id']}: held-out text appears in the prompt: {s[:80]!r}")


def messages_for_case(ds: dataset.Dataset, case: dict, template: str = TEMPLATE_VERSION) -> list[dict]:
    rules = ds.general_rules(case)
    messages = build_messages(dataset.grader_input(case), rules, template)
    check_no_leak(messages, case, rules)
    return messages


def messages_sha256(messages: list[dict]) -> str:
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def template_hash(general_rules: list[str], rules_source: str = dataset.RULES_DATASET,
                  template: str = TEMPLATE_VERSION) -> str:
    """Changes whenever anything that shapes the prompt changes, apart from the case itself.

    With per-case rules (Group A) the rules are part of each case, like its rubric: pass [] and
    rules_source=RULES_CASE. The prompts file hash and the dataset hash cover them.
    """
    parts = {
        "version": TEMPLATE_VERSION,
        "system": SYSTEM,
        "instruction": INSTRUCTION,
        "answer_layout": ANSWER_LAYOUT,
        "layout_verified": LAYOUT_VERIFIED,
        "general_rules": list(general_rules),
        "renderer": [inspect.getsource(f) for f in (norm, fmt, wrap, render_block, render_context,
                                                    render_output_format)],
        "wrap": WRAP,
        "levels": LEVELS,
    }
    if template == TRAIN_TEMPLATE_VERSION:  # eval-prompt-v3 keeps exactly the parts above
        parts.update({"version": TRAIN_TEMPLATE_VERSION, "system": TRAIN_SYSTEM,
                      "answer_layout": TRAIN_ANSWER_LAYOUT, "layout_verified": True})
    elif template != TEMPLATE_VERSION:
        raise PromptError(f"unknown prompt template {template!r}; choose from {list(TEMPLATES)}")
    if rules_source != dataset.RULES_DATASET:  # leaves the Group B hash as it was
        parts["general_rules_source"] = rules_source
    canonical = json.dumps(parts, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def dataset_template_hash(ds: dataset.Dataset, template: str = TEMPLATE_VERSION) -> str:
    if ds.group.rules_source == dataset.RULES_CASE:
        return template_hash([], dataset.RULES_CASE, template)
    return template_hash(ds.grading_policies, template=template)


def describe(ds: dataset.Dataset, template: str = TEMPLATE_VERSION) -> dict:
    """What a run config records about the prompt."""
    verified = True if template == TRAIN_TEMPLATE_VERSION else LAYOUT_VERIFIED
    if ds.group.rules_source == dataset.RULES_CASE:
        rule_sets = {json.dumps(ds.general_rules(c), ensure_ascii=False) for c in ds.cases}
        return {"template_version": template, "template_sha256": dataset_template_hash(ds, template),
                "layout_verified": verified, "general_rules_source": dataset.RULES_CASE,
                "general_rules_distinct_sets": len(rule_sets)}
    return {"template_version": template, "template_sha256": template_hash(ds.grading_policies, template=template),
            "layout_verified": verified, "general_rules_source": dataset.RULES_DATASET,
            "general_rules_count": len(ds.grading_policies)}


def build_prompts(ds: dataset.Dataset, template: str = TEMPLATE_VERSION) -> list[dict]:
    """One record per case, in dataset order: {test_id, messages, prompt_sha256}."""
    records = []
    for case in ds.cases:
        messages = messages_for_case(ds, case, template)
        records.append({"test_id": case["test_id"], "messages": messages,
                        "prompt_sha256": messages_sha256(messages)})
    return records


if __name__ == "__main__":
    import sys

    wanted = sys.argv[1:]
    groups = {"A" if t.startswith("csc236_A_") else "B" for t in wanted} or {"B"}
    if len(groups) != 1:
        sys.exit("give test_ids of one group at a time")
    ds = dataset.load_group(groups.pop())
    wanted = wanted or [ds.cases[0]["test_id"]]
    cases = ds.by_id()
    for tid in wanted:
        if tid not in cases:
            sys.exit(f"unknown test_id {tid}")
        for m in messages_for_case(ds, cases[tid]):
            print(f"===== {m['role']} =====\n{m['content']}")
    print(f"===== template {TEMPLATE_VERSION} sha256 {dataset_template_hash(ds)} "
          f"(layout verified: {LAYOUT_VERIFIED})")
