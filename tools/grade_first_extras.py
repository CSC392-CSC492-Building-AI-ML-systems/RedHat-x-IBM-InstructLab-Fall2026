"""Extensions to the grade-first generator (tools/gen_answers.py) for the ilab pipeline blocks.

gen_answers.py only changes parts of a correct answer that nothing else uses, at most two at a
time. That leaves gaps in the data (found in the stage 2 file): one criterion per skill is never
below full, no grade is below 30%, and no answer uses the wrong method. These extensions close
them while keeping the rule that every grade is decided before the answer is written:

1. More parts can be off. Where the rubric says "grade each criterion independently ... later
   criteria are graded on the student's own work", the induction hypothesis (C2) can be
   rewritten on its own, with one kind of mistake per level that the later parts don't depend
   on. Recurrences C1 can be "only one substitution" while the general form is still stated.
2. Up to three parts off at once, where a question has three safe parts.
3. Whole-answer mistakes whose grade the rubric's own general rule fixes:
     asymptotic          a larger c that works: C1 minimal, C2 minimal, C3 none (rule 1)
     recurrences         Master Theorem only: C1 none, C2 none, C3 full (rule 1)
     program_correctness a termination argument only: every criterion none (rule 1)
     induction_simple    another method (the rubric's own example): C1 kept, the rest none
     induction_complete  checking finitely many values: C1 kept, the rest none
     structural          induction on size/length (the rubric's own wording): C1 kept, the rest none
     every topic         a near-blank answer that restates the question: every criterion none
   A scenario is used only if its rule is in that question's rubric, and the code checks the
   rewritten answer (for example, that the new c is larger than the right one).
4. More variety: 8 reference styles instead of 5, including a student whose first language
   isn't English (the rubric doesn't grade English), rotated across questions; and a "none" whose
   rubric text offers a wrong alternative ("No proof, or the inequality is in the wrong
   direction") is written as that mistake half the time instead of being left out.
"""
from __future__ import annotations

import random
import re

import gen_answers as ga

EXTRA_STYLES = [
    "Write it as a student whose first language isn't English: the mathematics is fully correct and every "
    "step is there, but the sentences are short and simple, with a few small grammar mistakes (a missing "
    "article, a wrong verb form). The grammar mistakes must not change the mathematics.",
    "Write it like a hurried student: abbreviations such as WTS, IH, s.t. and =>, few full sentences, "
    "but every step is there and correct.",
    "Write it in a chatty way, like a student talking through their thinking, with every step present "
    "and correct.",
]
STYLES = ga.STYLES + EXTRA_STYLES

INDEPENDENT = re.compile(r"Grade each criterion independently", re.I)
# Extra parts that may be off, by topic: {criterion: {level: the one allowed kind of mistake}}.
# Each mistake leaves the work that later parts use in place.
EXTRA_SAFE = {
    "induction_simple": {"C2": {
        "partial": "States P(k) for an arbitrary k but never states the goal P(k + 1).",
        "minimal": "Says only \"assume it holds for k\", without writing out P(k) or saying k is arbitrary.",
        "none": "The hypothesis assumes the claim for every n, which is circular."}},
    "induction_complete": {"C2": {
        "partial": "Assumes P(i) for every i in the range, but the goal P(k + 1) is never stated.",
        "none": "The hypothesis assumes the statement being proved for every n."}},
    "structural_induction": {"C2": {
        "minimal": None,
        "none": "The hypothesis assumes the statement being proved for every element."}},
    "recurrences": {"C1": {
        "minimal": "Only one substitution before the general form, which is still stated correctly."}},
}
EXTRA_NEEDS = {  # what the rubric must say for EXTRA_SAFE to apply
    "induction_simple": INDEPENDENT, "induction_complete": INDEPENDENT, "structural_induction": INDEPENDENT,
    "recurrences": re.compile(r"Only one substitution", re.I),
}


def style_for(seed_id: str, k: int) -> str:
    return STYLES[(ga.stable_int(seed_id, "style") + k) % len(STYLES)]


def _flat(text: str) -> str:
    return " ".join(str(text).split())


def safe_parts_plus(seed: dict, ref: dict) -> dict:
    """gen_answers.safe_parts plus EXTRA_SAFE where the rubric allows it."""
    table = ga.safe_parts(seed, ref)
    extra, need = EXTRA_SAFE.get(seed["topic"], {}), EXTRA_NEEDS.get(seed["topic"])
    if need is None or not need.search(_flat(seed["rubric_text"])):
        return table
    crits = {c["id"]: c for c in seed["criteria"]}
    for cid, levels in extra.items():
        if cid not in crits:
            continue
        have = table.setdefault(cid, {})
        for lv, mistake in levels.items():
            if lv in crits[cid]["levels"] and lv not in have:
                have[lv] = mistake
    return table


# ----------------------------------------------------------------------------- scenarios

def _rule(seed, pattern):
    m = re.search(pattern, _flat(seed["rubric_text"]), re.I)
    return m


def _true_c(seed):
    m = re.search(r"c = (\d+) with a valid n_0", _flat(seed["criteria"][0]["levels"]["full"]["text"]))
    return int(m.group(1)) if m else None


def _plain(text):
    return re.sub(r"[$\\{}]", "", text)


def scenarios_for(seed: dict) -> list[dict]:
    """The whole-answer scenarios this question's rubric fixes the grade for."""
    ids = [c["id"] for c in seed["criteria"]]
    crit = {c["id"]: c for c in seed["criteria"]}
    rest_none = {c: ("full" if c == ids[0] else "none") for c in ids}
    out, topic = [], seed["topic"]

    if topic == "asymptotic_analysis" and _rule(seed, r"picks a larger c can earn at most minimal on C2") \
            and _true_c(seed) and len(ids) == 3:
        tc = _true_c(seed)

        def larger_c(text, tc=tc):
            cs = re.findall(r"\bc\s*=\s*(\d+)", _plain(text))
            return bool(cs) and int(cs[0]) > tc and str(int(cs[0]) - 1) in _plain(text)
        out.append({"name": "larger_c", "keep_first": False, "levels": {"C1": "minimal", "C2": "minimal", "C3": "none"},
                    "check": larger_c,
                    "instruction": "Rewrite the whole answer so that the student picks a constant c that works but is "
                                   "larger than the smallest one (for example, found by bounding each term of f(n) by a "
                                   "multiple of g(n)), gives a valid n_0 for that constant, proves correctly that their "
                                   "c and n_0 work, and then argues that their own c - 1 (one less than their constant) "
                                   "fails, as if it were the smallest."})
    if topic == "recurrences" and _rule(seed, r"Master Theorem alone earns 0 for C1 and C2"):
        out.append({"name": "master_theorem_only", "keep_first": False,
                    "levels": {c: ("full" if c == ids[-1] else "none") for c in ids},
                    "check": lambda text, seed=seed: "master" in text.lower() and not re.search(r"\^\s*\(?i\b", text)
                    and ga.rewrite_still_right(seed, ids[-1], text),
                    "instruction": "Replace the whole answer with a solution that applies the Master Theorem directly: "
                                   "name a, b and f(n), compare f(n) with n^(log_b a), and state the same tight bound as "
                                   "the correct answer. Do no repeated substitution and give no exact closed form."})
    if topic == "program_correctness" and _rule(seed, r"termination argument alone .{0,60}earns 0 on every criterion"):
        out.append({"name": "termination_only", "keep_first": False, "levels": {c: "none" for c in ids},
                    "check": lambda text: re.search(r"decreas|terminat", text, re.I) is not None
                    and re.search(r"invariant|\binv\b|postcondition", text, re.I) is None,
                    "instruction": "Replace the whole answer with only a termination argument: name a quantity that "
                                   "decreases on every iteration and explain why the loop must stop. Say nothing about "
                                   "the invariant or the postcondition."})
    no_induction = lambda text: re.search(r"hypothes|inductive step|induction step|assume p\(", text, re.I) is None
    m = _rule(seed, r"A proof by another method \(for example, ([^)]*)\) earns 0 for C2 and C3")
    if topic == "induction_simple" and m:
        out.append({"name": "other_method", "keep_first": True, "levels": rest_none, "check": no_induction,
                    "instruction": f"Keep part {ids[0]} as it is. Replace everything after it with a proof by another "
                                   f"method instead of induction: {m.group(1)}. Write no induction hypothesis and no "
                                   "inductive step."})
    if topic == "induction_complete" and _rule(seed, r"Checking finitely many values.{0,80}earns credit only under C1"):
        out.append({"name": "finite_check", "keep_first": True, "levels": rest_none, "check": no_induction,
                    "instruction": f"Keep part {ids[0]} as it is. Replace everything after it with a check of the next "
                                   "few values (a short table or list) and a claim that the pattern continues. Write no "
                                   "induction hypothesis and no inductive step."})
    m = _rule(seed, r"A proof by (induction on the [^,]+), or any other method, earns 0 for "
                    r"(?:every criterion except C1|C2, C3 and C4)")
    if topic == "structural_induction" and m:
        out.append({"name": "wrong_induction", "keep_first": True, "levels": rest_none,
                    "check": lambda text: re.search(r"induction on", text, re.I) is not None
                    and "structural" not in text.lower(),
                    "instruction": f"Keep part {ids[0]} as it is. Replace everything after it with a proof by "
                                   f"{m.group(1)} instead of structural induction, written as a plausible student "
                                   "attempt."})
    none_ok = all(re.search(r"\b(no|not|missing|absent|empty)\b", crit[c]["levels"]["none"]["text"], re.I)
                  for c in ids if "none" in crit[c]["levels"])
    if none_ok and all("none" in crit[c]["levels"] for c in ids):
        out.append({"name": "near_blank", "keep_first": False, "levels": {c: "none" for c in ids},
                    "check": lambda text: 0 < len(text) < 450,
                    "instruction": "Replace the whole answer with a very weak one: restate what the question asks in "
                                   "your own words and add one or two vague sentences, with no real work (no base case, "
                                   "no constants, no proof steps)."})
    return out


def scenario_prompt(seed: dict, ref_parts: dict, sc: dict) -> str:
    shown = "\n".join(f"<<{cid}>>\n{text}" for cid, text in ref_parts.items())
    first = list(ref_parts)[0]
    returns = (f"Return only the text that comes after part {first}" if sc["keep_first"]
               else "Return only the new answer")
    return (
        f"Below is an exam question, its grading rubric, and a correct student answer split into parts.\n\n"
        f"{ga.question_and_rubric(seed)}\n\nCorrect answer:\n{shown}\n\n{sc['instruction']}\n\n"
        "The new answer must read like a real student's attempt, in the same style as the correct answer. Do not "
        "say or hint that anything is wrong, and do not mention the rubric, the criteria or marks. "
        f"{returns}, with no markers, no labels and no explanation."
    )


def none_alternative(text: str) -> str | None:
    """'No proof, or the inequality is in the wrong direction.' -> 'the inequality is in the wrong direction'."""
    if ", or " not in text:
        return None
    alt = text.split(", or ", 1)[1].strip().rstrip(".")
    return alt[0].upper() + alt[1:] + "." if alt else None


# ----------------------------------------------------------------------------- planning

def plan(seed: dict, refs: list[dict], n: int, global_seed: int) -> list[dict]:
    """Like gen_answers.make_targets, with up to three parts off and whole-answer scenarios.
    About 20% all full, 15% scenarios, 10% three off, 25% two off and the rest one off."""
    rng = random.Random(ga.stable_int(seed["seed_id"], global_seed, "extras"))
    crits = [c["id"] for c in seed["criteria"]]
    scen = scenarios_for(seed)
    n_full = round(0.20 * n)
    n_scen = min(round(0.15 * n), 2 * len(scen)) if scen else 0
    n_three = round(0.10 * n)
    n_two = round(0.25 * n)
    n_one = max(0, n - n_full - n_scen - n_three - n_two)
    kinds = ["full"] * n_full + ["scenario"] * n_scen + ["three"] * n_three + ["two"] * n_two + ["one"] * n_one
    kinds = kinds[:n]
    order = crits[:]
    rng.shuffle(order)
    targets, one_i, scen_i = [], 0, 0
    for i, kind in enumerate(kinds):
        ref = refs[i % len(refs)]
        if kind == "scenario":
            sc = scen[scen_i % len(scen)]
            scen_i += 1
            targets.append((ref["ref_id"], dict(sc["levels"]), sc["name"]))
            continue
        safe = safe_parts_plus(seed, ref)
        ids = [c for c in order if c in safe and safe[c]]
        k = min({"full": 0, "one": 1, "two": 2, "three": 3}[kind], len(ids))
        t = {c: "full" for c in crits}
        if k == 1:
            cid = ids[one_i % len(ids)]
            levels = [lv for lv in ga.OFF_LEVELS if lv in safe[cid]]
            t[cid] = levels[(one_i // len(ids) + one_i) % len(levels)]
            one_i += 1
        elif k >= 2:
            for cid in rng.sample(ids, k):
                t[cid] = rng.choice([lv for lv in ga.OFF_LEVELS if lv in safe[cid]])
        targets.append((ref["ref_id"], t, ""))
    flawed = [i for i, (_, t, _) in enumerate(targets) if any(v != "full" for v in t.values())]
    tricks = set(rng.sample(flawed, min(len(flawed), round(0.15 * n))))
    return [{"ref_id": ref_id, "target": t, "scenario": name,
             "trick": rng.choice(ga.TRICKS) if i in tricks else None, "trick_at_start": rng.random() < 0.3}
            for i, (ref_id, t, name) in enumerate(targets)]
