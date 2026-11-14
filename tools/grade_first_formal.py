"""Grade-first answers for the DFA and regex grading skills, checked by code.

gen_answers.py changes one part of a correct answer at a time. That doesn't work for these two
topics, because every criterion grades the same machine or expression. But a DFA or a regular
expression can be run, so here the code does the checking.

DFA (topic dfa_nfa). The teacher writes correct reference DFAs in a fixed layout. The code
  checks each one against the DFA in the rubric (states may be renamed, as rubric rule 2 says),
  then makes the mistakes itself: it points transitions to the wrong state (C1), changes the
  accepting states (C2), and removes or duplicates transitions (C3). It writes the result in one
  of four layouts (lines of arrows, δ(q, a) = r, a transition table, or sentences), keeping a
  layout only if reading it back gives the same DFA, and grades it the way the rubric describes,
  so every level in the label is computed, not guessed. The teacher only writes the references
  and the one-sentence reasons, and is told what the code changed (dfa_facts).

Regex (topic regex). The teacher writes correct references; the code checks them on every string
  up to length 10 against the question's language. For a flawed answer the grade is chosen first
  and the teacher rewrites the expression (and the explanation) to fit it. The code then checks
  the rewrite: a "full" soundness or completeness must really be sound or complete, a "none"
  soundness must match every string, and anything in between must really be unsound or
  incomplete. Whether a flaw is "partial" (one kind of wrong string) or "minimal" (several) can't
  be decided by code, so the teacher grades those criteria blind, given the shortest strings the
  code found that the regex gets wrong (regex_facts), and the rewrite is kept only if it agrees.

Used by tools/grade_first_blocks.py for these topics.
"""
from __future__ import annotations

import itertools
import random
import re

import gen_answers as ga

FORMAL_TOPICS = ("dfa_nfa", "regex")


def _flat(text):
    return " ".join(str(text).split())


def _level_text(seed, cid, lv):
    c = next((c for c in seed["criteria"] if c["id"] == cid), None)
    return _flat(c["levels"][lv]["text"]) if c and lv in c["levels"] else ""


# ============================================================================== DFA

NAME = r"[A-Za-z_][\w']*"
DFA_TEMPLATE = {  # rubric texts the DFA grader relies on
    ("C1", "partial"): "Exactly one transition written goes to the wrong state",
    ("C2", "partial"): "together with another state",
    ("C3", "partial"): "Exactly one transition is missing or duplicated",
}


def rubric_dfa(seed: dict) -> dict | None:
    """The DFA in the rubric's C1 full text and the accepting state(s) from C2's."""
    if any(t not in _level_text(seed, c, lv) for (c, lv), t in DFA_TEMPLATE.items()):
        return None
    c1 = _level_text(seed, "C1", "full")
    if "renaming of states:" not in c1:
        return None
    spec = c1.split("renaming of states:", 1)[1].split(". ", 1)[0]
    states, start, delta = [], None, {}
    for chunk in spec.split(";"):
        m = re.match(rf"\s*({NAME})\s*(\(start\))?\s*:\s*(.+)", chunk)
        if not m:
            return None
        q = m.group(1)
        states.append(q)
        if m.group(2):
            start = q
        for sym, tgt in re.findall(rf"(\S+)\s*->\s*({NAME})", m.group(3)):
            delta[(q, sym)] = tgt
    m = re.search(r"\(([^)]*) in the DFA above\)", _level_text(seed, "C2", "full"))
    accepting = set(re.findall(NAME, m.group(1))) & set(states) if m else set()
    alphabet = sorted({s for _, s in delta})
    if not start or not accepting or len(delta) != len(states) * len(alphabet):
        return None
    return {"states": states, "start": start, "accepting": accepting, "alphabet": alphabet, "delta": delta}


STOP = {"and", "or", "the", "states", "state", "State", "States", "is", "are", "none", "None", "no", "No", "empty",
          "only", "DFA", "has", "two", "three", "four", "with", "start", "Start", "accepting", "Accepting", "a", "an",
          "set", "of", "its", "it", "both", "also", "there", "There", "The", "We", "we", "machine"}


def _names(text):
    return [n for n in re.findall(NAME, text) if n not in STOP]


def parse_dfa(text: str) -> dict:
    """The DFA in an answer: states, start, accepting, transitions [(q, sym, target)], other sentences.
    Reads "States: ...", "Start state is q0", "Accepting states are q1 and q2", "q0 (start and
    accepting)", "q0: 0 -> q1, 1 -> q0", "q0 on a goes to q1" and "δ(q0, a) = q1"."""
    out = {"states": [], "start": None, "accepting": set(), "has_accepting_line": False, "trans": [], "prose": []}
    table_syms, table_states = None, []
    for line in text.splitlines():
        row = line.strip()
        if row.startswith("|"):  # a transition table: | state | a | b |, with → for start and * for accepting
            cells = [c.strip() for c in row.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            if table_syms is None:
                table_syms = [c.strip("` ") for c in cells[1:]]
                continue
            note = cells[0]
            name = re.sub(r"\([^)]*\)|→|->|>|\*", "", note).strip(" `")
            if not re.fullmatch(NAME, name):
                continue
            marks = note.replace(name, " ")  # a state may be named s_start or acc
            if re.search(r"→|->|>|\bstart", marks, re.I):
                out["start"] = name
            if re.search(r"\*|\baccept", marks, re.I):
                out["accepting"].add(name)
                out["has_accepting_line"] = True
            table_states.append(name)
            for sym, cell in zip(table_syms, cells[1:]):
                for tgt in re.findall(NAME, cell):  # "-" or an empty cell: no transition
                    if tgt not in STOP:
                        out["trans"].append((name, sym, tgt))
            continue
        for s in re.split(r"(?<=\.)\s+(?=[A-Z])", line.strip()):
            s = s.strip()
            if not s:
                continue
            m = re.match(rf"({NAME})\s*:\s*(.*->.*)$", s)
            if m:
                for sym, tgt in re.findall(rf"(\S+?)\s*->\s*({NAME})", m.group(2)):
                    out["trans"].append((m.group(1), sym, tgt))
                continue
            prose_t = (re.findall(rf"({NAME})\s+on\s+(\S+?)\s+(?:goes|moves|go|transitions?)\s+to\s+({NAME})", s)
                       + re.findall(rf"δ\(\s*({NAME})\s*,\s*(\S+?)\s*\)\s*=\s*({NAME})", s))
            for q, sym, tgt in prose_t:
                out["trans"].append((q, sym.strip(",.:"), tgt))
            for name, note in re.findall(rf"({NAME})\s*\(([^)]*)\)", s):
                if name in STOP:
                    continue
                if "start" in note.lower():
                    out["start"] = name
                if "accept" in note.lower():
                    out["accepting"].add(name)
                    out["has_accepting_line"] = True
            m = re.search(r"(?i)\baccept(?:ing)?(?:\s+states?)?\s*(?:[:=]|\bis\b|\bare\b)\s*(.*)$", s)
            if m:
                out["has_accepting_line"] = True
                out["accepting"] |= set(_names(m.group(1).rstrip(".")))
                continue
            m = re.search(rf"(?i)\bstart(?:ing)?(?:\s+state)?\s*(?:[:=]|\bis\b)\s*({NAME})", s)
            if m and m.group(1) not in STOP:
                out["start"] = m.group(1)
                continue
            m = (re.match(r"(?i)states?\s*(?:[:=]|\bare\b)\s*(.+)$", s)
                 or re.search(r"(?i)\bhas\s+(?:\w+\s+)?states?\s*:?\s*(.+)$", s))
            if m and not prose_t:
                body = re.sub(r"\([^)]*\)", "", m.group(1).rstrip("."))
                out["states"] = _names(body) or out["states"]
                continue
            if not prose_t:
                out["prose"].append(s)
    if not out["states"] and table_states:
        out["states"] = table_states
    if not out["states"]:
        seen = []
        for q, _, t in out["trans"]:
            for x in (q, t):
                if x not in seen:
                    seen.append(x)
        out["states"] = seen
    return out


def _level_by_count(n):
    return "full" if n == 0 else "partial" if n == 1 else "minimal"


def grade_dfa(student: dict, ref: dict) -> dict:
    """{C1, C2, C3: level} by the rubric, with the details used."""
    if not student["trans"]:
        return {"C1": "none", "C2": "none" if not student["accepting"] else "minimal", "C3": "none",
                "detail": "no transitions", "mapping": None}
    targets = {}
    for q, sym, t in student["trans"]:
        targets.setdefault((q, sym), []).append(t)
    pairs = [(q, sym) for q in student["states"] for sym in ref["alphabet"]]
    flaws = sum(1 for p in pairs if p not in targets) + sum(len(v) - 1 for v in targets.values() if len(v) > 1)
    single = {p: v[0] for p, v in targets.items() if len(v) == 1}
    best = None
    sts = student["states"]
    if len(sts) == len(ref["states"]):
        for perm in itertools.permutations(ref["states"]):
            mp = dict(zip(sts, perm))
            if student["start"] and mp.get(student["start"]) != ref["start"]:
                continue
            wrong = sum(1 for (q, sym), t in single.items()
                        if q in mp and t in mp and ref["delta"].get((mp[q], sym)) != mp[t]) \
                + sum(1 for (q, sym), t in single.items() if q not in mp or t not in mp)
            acc = {mp[a] for a in student["accepting"] if a in mp}
            c2 = ("none" if not acc else "full" if acc == ref["accepting"] else
                  "partial" if ref["accepting"] <= acc else "minimal")
            key = (wrong, ["full", "partial", "minimal", "none"].index(c2))
            if best is None or key < best[0]:
                best = (key, wrong, c2, mp)
    if best is None:  # a different number of states: no renaming fits the rubric's DFA
        return {"C1": "none", "C2": "none" if not student["accepting"] else "minimal",
                "C3": _level_by_count(flaws), "detail": "state count differs from the rubric's DFA", "mapping": None}
    _, wrong, c2, mp = best
    c1 = "minimal" if not student["start"] else _level_by_count(wrong)
    return {"C1": c1, "C2": c2, "C3": _level_by_count(flaws),
            "detail": f"{wrong} wrong transitions, {flaws} missing or duplicated, start {student['start']}, "
                      f"renaming {mp}", "mapping": mp}


DFA_LAYOUTS = ("list", "delta", "table", "prose")  # ways students write a DFA; parse_dfa reads all four


def _and(names):
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def render_dfa(d: dict, keep_accepting_line=True, layout="list") -> str:
    """The DFA written in one of DFA_LAYOUTS, followed by the sentences about what the states mean."""
    acc = [a for a in d["states"] if a in d["accepting"]]
    by_state = {}
    for q, sym, t in d["trans"]:
        by_state.setdefault(q, []).append((sym, t))
    syms = sorted({sym for _, sym, _ in d["trans"]})
    if layout == "table":
        lines = ["| state | " + " | ".join(syms) + " |", "|---|" + "---|" * len(syms)]
        for q in d["states"]:
            name = ("→ " if q == d["start"] else "") + q + (" *" if q in d["accepting"] else "")
            cells = [", ".join(t for s, t in by_state.get(q, []) if s == sym) or "-" for sym in syms]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        legend = [x for x, on in (("→ marks the start state", d["start"]), ("* marks the accepting states", acc)) if on]
        if legend:
            lines.append(" and ".join(legend) + ".")
        if keep_accepting_line and not acc:
            lines.append("Accepting states: none")
        return "\n".join(lines + d["prose"])
    if layout in ("delta", "prose"):
        lines = [f"States: {', '.join(d['states'])}." if layout == "delta" else f"The DFA has states {_and(d['states'])}."]
        if d["start"]:
            lines.append(f"The start state is {d['start']}.")
        if keep_accepting_line:
            lines.append(f"The accepting state is {acc[0]}." if len(acc) == 1 else
                         f"The accepting states are {_and(acc)}." if acc else "Accepting states: none")
        for q in d["states"]:
            if q in by_state:
                if layout == "delta":
                    lines.append(", ".join(f"δ({q}, {sym}) = {t}" for sym, t in by_state[q]))
                else:
                    lines.append(", and ".join(f"{q} on {sym} goes to {t}" for sym, t in by_state[q]) + ".")
        return "\n".join(lines + d["prose"])
    lines = [f"States: {', '.join(d['states'])}"]
    if d["start"]:
        lines.append(f"Start state: {d['start']}")
    if keep_accepting_line:
        lines.append(f"Accepting states: {', '.join(acc) or 'none'}")
    for q in d["states"]:
        if q in by_state:
            lines.append(f"{q}: {', '.join(f'{sym} -> {t}' for sym, t in by_state[q])}")
    return "\n".join(lines + d["prose"])


def same_dfa(a: dict, b: dict) -> bool:
    return (sorted(a["trans"]) == sorted(b["trans"]) and a["start"] == b["start"]
            and set(a["accepting"]) == set(b["accepting"]) and list(a["states"]) == list(b["states"]))


def dfa_reference_prompt(seed: dict, style: str) -> str:
    return (
        f"Below is an exam question and its grading rubric.\n\n{ga.question_and_rubric(seed)}\n\n"
        "Write a complete and correct answer, as a strong student would write it, that earns full marks on every "
        f"criterion. {style} You may name the states however you like.\n\nUse exactly this layout, with nothing "
        "before it:\nStates: <the states, separated by commas>\nStart state: <one state>\n"
        "Accepting states: <the accepting states, separated by commas>\nthen one line per state, such as "
        "\"q0: 0 -> q1, 1 -> q0\" (with the question's symbols), and after those at most two short sentences saying "
        "what each state means. Those sentences must not say which states are accepting and must not repeat any "
        "transition. Do not mention the rubric, the criteria or marks."
    )


def check_dfa_reference(seed: dict, text: str) -> dict:
    ref = rubric_dfa(seed)
    if ref is None:
        return {"result": "not usable", "note": "the rubric's DFA couldn't be read"}
    d = parse_dfa(text)
    g = grade_dfa(d, ref)
    ok = g["C1"] == g["C2"] == g["C3"] == "full" and not any("accept" in p.lower() or "->" in p for p in d["prose"])
    return {"result": "right" if ok else "wrong", "note": f"{g['C1']}/{g['C2']}/{g['C3']} ({g['detail']})"}


RENAMES = [None, list("ABCDEF"), [f"s{i}" for i in range(6)], ["p", "q", "r", "s", "t", "u"]]


def _rename(d: dict, mapping: dict) -> dict:
    sub = lambda x: mapping.get(x, x)
    prose = [re.sub(rf"\b({'|'.join(map(re.escape, sorted(mapping, key=len, reverse=True)))})\b",
                    lambda m: mapping[m.group(1)], p) for p in d["prose"]] if mapping else list(d["prose"])
    return {**d, "states": [sub(q) for q in d["states"]], "start": sub(d["start"]) if d["start"] else None,
            "accepting": {sub(a) for a in d["accepting"]}, "trans": [(sub(q), s, sub(t)) for q, s, t in d["trans"]],
            "prose": prose}


def mutate_dfa(base: dict, want: dict, rng: random.Random) -> tuple[dict, list[str], bool]:
    """Apply the mistakes for the wanted levels ({C1, C2, C3}: level). Returns (dfa, notes, accepting line)."""
    d = {**base, "trans": list(base["trans"]), "accepting": set(base["accepting"])}
    notes, keep_acc_line = [], True
    if want.get("C3") in ("partial", "minimal"):
        picked = rng.sample(range(len(d["trans"])), min(len(d["trans"]), 1 if want["C3"] == "partial" else 2))
        new = []
        for i, (q, sym, t) in enumerate(d["trans"]):
            if i not in picked:
                new.append((q, sym, t))
            elif rng.random() < 0.5:
                notes.append(f"{q} has no transition on {sym}")
            else:
                other = rng.choice([x for x in d["states"] if x != t])
                new += [(q, sym, t), (q, sym, other)]
                notes.append(f"{q} has two transitions on {sym}, to {t} and to {other}")
        d["trans"] = new
    if want.get("C1") in ("partial", "minimal"):
        if want["C1"] == "minimal" and rng.random() < 0.4:
            d["start"] = None
            notes.append("no start state is given")
        else:
            singles = {}
            for q, sym, t in d["trans"]:
                singles[(q, sym)] = singles.get((q, sym), 0) + 1
            chosen = [p for p in singles if singles[p] == 1]
            rng.shuffle(chosen)
            for q, sym in chosen[:1 if want["C1"] == "partial" else 2]:
                for j, (q2, s2, t2) in enumerate(d["trans"]):
                    if (q2, s2) == (q, sym):
                        other = rng.choice([x for x in d["states"] if x != t2])
                        d["trans"][j] = (q, sym, other)
                        notes.append(f"{q} on {sym} goes to {other}, where the correct DFA goes to {t2}")
    if want.get("C2") in ("partial", "minimal", "none"):
        others = [x for x in d["states"] if x not in d["accepting"]]
        if want["C2"] == "partial" and others:
            extra = rng.choice(others)
            d["accepting"] |= {extra}
            notes.append(f"{extra} is accepting as well as the correct accepting state(s) "
                         f"{_and(sorted(base['accepting']))}")
        elif want["C2"] == "minimal" and others:
            d["accepting"] = set(rng.sample(others, rng.randint(1, len(others))))
            notes.append(f"the accepting states given are {_and(sorted(d['accepting']))}, but the correct DFA "
                         f"accepts in {_and(sorted(base['accepting']))} instead")
        elif want["C2"] == "none":
            d["accepting"] = set()
            keep_acc_line = rng.random() < 0.5
            notes.append("no accepting state is given")
    return d, notes, keep_acc_line


def dfa_facts(levels: dict, notes: list[str]) -> str:
    """What the code knows about a built DFA answer, for the teacher writing the reasons."""
    lines = []
    if levels.get("mapping"):
        lines.append("- The answer's states correspond to the DFA in the rubric as "
                     + ", ".join(f"{k} = {v}" for k, v in levels["mapping"].items()) + ".")
    lines += [f"- {n}." for n in notes]  # not capitalized: a note can start with a state name like p
    if not notes:
        lines.append("- The DFA is correct: the start state, every transition and the accepting states match the "
                     "DFA in the rubric.")
    return "\n".join(lines)


def dfa_plan(seed: dict, refs: list[dict], n: int, global_seed: int) -> list[dict]:
    """Answers built and graded entirely by code. About 20% full, 35% one criterion off, 25% two,
    15% three and 5% only a description with no machine."""
    rubric = rubric_dfa(seed)
    rng = random.Random(ga.stable_int(seed["seed_id"], global_seed, "dfa"))
    kinds = (["full"] * round(0.20 * n) + ["blank"] * max(1, round(0.05 * n)) + ["three"] * round(0.15 * n)
             + ["two"] * round(0.25 * n))
    kinds = (kinds + ["one"] * n)[:n]
    off_levels = {"C1": ["partial", "minimal"], "C2": ["partial", "minimal", "none"], "C3": ["partial", "minimal"]}
    out = []
    for i, kind in enumerate(kinds):
        ref = refs[i % len(refs)]
        base = parse_dfa(ref["text"])
        names = RENAMES[rng.randrange(len(RENAMES))]
        if names:
            base = _rename(base, dict(zip(base["states"], names)))
        layout = "list"
        if kind == "blank":
            d = {**base, "trans": [], "start": None, "accepting": set()}
            answer = "\n".join(base["prose"]) or "The DFA remembers what it has seen so far."
            notes = ["the answer only describes what the states mean: it gives no transitions, no start state "
                     "and no accepting states"]
        else:
            k = {"full": 0, "one": 1, "two": 2, "three": 3}[kind]
            want = {c: rng.choice(off_levels[c]) for c in rng.sample(["C1", "C2", "C3"], k)}
            d, notes, keep = mutate_dfa(base, want, rng)
            # Written in one of several layouts; the layout is used only if reading it back gives the same DFA.
            layout = DFA_LAYOUTS[ga.stable_int(seed["seed_id"], i, "layout", global_seed) % len(DFA_LAYOUTS)]
            answer = render_dfa(d, keep, layout)
            if not same_dfa(parse_dfa(answer), d):
                layout, answer = "list", render_dfa(d, keep)
        levels = grade_dfa(parse_dfa(answer), rubric)
        out.append({"ref_id": ref["ref_id"], "target": {c: levels[c] for c in ("C1", "C2", "C3")},
                    "scenario": "", "prebuilt": answer, "facts": dfa_facts(levels, notes),
                    "check": f"computed by code ({layout} layout): {levels['detail']}; what is wrong: "
                             f"{'; '.join(notes) or 'nothing'}"})
    flawed = [i for i, t in enumerate(out) if any(v != "full" for v in t["target"].values())]
    tricks = set(rng.sample(flawed, min(len(flawed), round(0.15 * n))))
    for i, t in enumerate(out):
        t["trick"] = rng.choice(ga.TRICKS) if i in tricks else None
        t["trick_at_start"] = rng.random() < 0.3
    return out


# ============================================================================== regex

REGEX_LANGUAGES = [  # (pattern in the question, alphabet, membership)
    (r"even number of 0s|number of 0s is even", "01", lambda s: s.count("0") % 2 == 0),
    (r"end with 01", "01", lambda s: s.endswith("01")),
    (r"length is a multiple of 3", "01", lambda s: len(s) % 3 == 0),
    (r"start and end with the same symbol", "ab", lambda s: len(s) > 0 and s[0] == s[-1]),
    (r"exactly one b", "ab", lambda s: s.count("b") == 1),
    (r"do not contain 00", "01", lambda s: "00" not in s),
]
MAX_LEN = 10


def regex_language(seed: dict):
    q = _flat(seed["question"])
    for pat, alphabet, member in REGEX_LANGUAGES:
        if re.search(pat, q):
            return alphabet, member
    return None


def regex_of(text: str) -> str | None:
    m = re.search(r"(?m)^\s*(\*\*)?\s*[$`]*\s*r\s*=\s*(.+?)\s*$", text)
    if not m:
        return None
    rx = m.group(2)
    if m.group(1) and rx.endswith("**"):  # the line was written in bold
        rx = rx[:-2]
    rx = re.split(r"\s+(?:because|since|where|which|and)\b|,\s|;\s", rx)[0]
    rx = rx.replace("\\varepsilon", "ε").replace("\\epsilon", "ε").replace("\\cup", "+").replace("|", "+")
    rx = rx.replace("∪", "+").replace("·", "")
    rx = re.sub(r"[$\\{}`]", "", rx).replace("^", "").replace(" ", "").rstrip(".,;")
    return rx or None


def classify(rx: str, alphabet: str, member) -> dict | None:
    """sound, complete and everything for a regex in the course's notation, on all strings up to MAX_LEN."""
    if rx is None or set(rx) - set(alphabet + "+()*ε"):
        return None
    try:
        r = re.compile("(?:" + rx.replace("+", "|").replace("ε", "(?:)") + r")\Z")
    except re.error:
        return None
    strings = [""] + ["".join(p) for n in range(1, MAX_LEN + 1) for p in itertools.product(alphabet, repeat=n)]
    acc = [s for s in strings if r.match(s)]
    accs = set(acc)
    extra = [s for s in acc if not member(s)]
    missed = [s for s in strings if member(s) and s not in accs]
    return {"sound": not extra, "complete": not missed, "everything": len(acc) == len(strings),
            "extra": extra[:8], "n_extra": len(extra), "missed": missed[:8], "n_missed": len(missed)}


def regex_facts(rx: str, cls: dict | None, alphabet: str) -> str:
    """What running the student's regex showed, for the level check and the reasons."""
    if cls is None:
        return ""
    show = lambda xs: ", ".join(x or "ε" for x in xs)
    lines = [f"- The student's regular expression is r = {rx}. It was run by code on every string over "
             f"{{{', '.join(alphabet)}}} up to length {MAX_LEN}:"]
    lines.append(f"- r matches {cls['n_extra']} string(s) that are not in L; the shortest are: {show(cls['extra'])}."
                 if cls["n_extra"] else "- r matches no string outside L.")
    lines.append(f"- r misses {cls['n_missed']} string(s) of L; the shortest are: {show(cls['missed'])}."
                 if cls["n_missed"] else "- r matches every string in L.")
    return "\n".join(lines)


def regex_ok_for(levels: dict, cls: dict | None) -> bool:
    if cls is None:
        return False
    c1, c2 = levels["C1"], levels["C2"]
    ok1 = (cls["sound"] if c1 == "full" else cls["everything"] if c1 == "none"
           else not cls["sound"] and not cls["everything"])
    ok2 = cls["complete"] if c2 == "full" else not cls["complete"]
    return ok1 and ok2


def regex_self_check(seed: dict) -> str | None:
    """None if the code's language agrees with the rubric's own example regexes, else why not."""
    lang = regex_language(seed)
    if lang is None:
        return "the question's language isn't in REGEX_LANGUAGES"
    m = re.search(r"For example, (.+?) is sound", _level_text(seed, "C1", "full"))
    if m:
        cls = classify(m.group(1).replace(" ", ""), *lang)
        if cls is not None and not cls["sound"]:
            return f"the rubric's sound example {m.group(1)} isn't sound for the language in REGEX_LANGUAGES"
    return None


def regex_reference_prompt(seed: dict, style: str) -> str:
    return (
        f"Below is an exam question and its grading rubric.\n\n{ga.question_and_rubric(seed)}\n\n"
        "Write a complete and correct answer, as a strong student would write it, that earns full marks on every "
        f"criterion. {style}\n\nStart with one line of the form \"r = <your regular expression>\", in plain text "
        "with + for union, * for star, juxtaposition for concatenation and ε for the empty string (no LaTeX). Then "
        "explain why L(r) = L, covering both directions. Do not mention the rubric, the criteria or marks."
    )


def check_regex_reference(seed: dict, text: str) -> dict:
    problem = regex_self_check(seed)
    if problem:
        return {"result": "not usable", "note": problem}
    rx = regex_of(text)
    cls = classify(rx, *regex_language(seed))
    ok = bool(cls and cls["sound"] and cls["complete"])
    return {"result": "right" if ok else "wrong",
            "note": f"r = {rx}: " + (f"sound {cls['sound']}, complete {cls['complete']}" if cls else "couldn't read it")}


REGEX_PAIRS = [("partial", "full"), ("minimal", "full"), ("full", "partial"), ("full", "minimal"),
               ("partial", "partial"), ("partial", "minimal"), ("minimal", "partial"), ("minimal", "minimal"),
               ("none", "full")]


def regex_plan(seed: dict, refs: list[dict], n: int, global_seed: int) -> list[dict]:
    """Grades chosen first: about 20% full, 15% only the explanation off, the rest a flawed regex.
    The explanation level must fit the regex: it can't be full if the regex is wrong, and it can't
    explain one direction correctly if both directions are wrong."""
    rng = random.Random(ga.stable_int(seed["seed_id"], global_seed, "regex"))
    kinds = ["full"] * round(0.20 * n) + ["explanation"] * round(0.15 * n)
    kinds = (kinds + ["regex"] * n)[:n]
    out = []
    for i, kind in enumerate(kinds):
        ref = refs[i % len(refs)]
        if kind == "full":
            t = {"C1": "full", "C2": "full", "C3": "full"}
        elif kind == "explanation":
            t = {"C1": "full", "C2": "full", "C3": rng.choice(["partial", "minimal", "none"])}
        else:
            c1, c2 = REGEX_PAIRS[i % len(REGEX_PAIRS)]
            both_wrong = c1 in ("partial", "minimal") and c2 != "full"
            t = {"C1": c1, "C2": c2, "C3": rng.choice(["minimal", "none"] if both_wrong else ["partial", "minimal", "none"])}
        out.append({"ref_id": ref["ref_id"], "target": t, "scenario": "", "prebuilt": "", "check": ""})
    flawed = [i for i, t in enumerate(out) if any(v != "full" for v in t["target"].values())]
    tricks = set(rng.sample(flawed, min(len(flawed), round(0.15 * n))))
    for i, t in enumerate(out):
        t["trick"] = rng.choice(ga.TRICKS) if i in tricks else None
        t["trick_at_start"] = rng.random() < 0.3
    return out


def regex_rewrite_prompt(seed: dict, ref_text: str, t: dict) -> str:
    lt = lambda c: f"\"{t[c]}\" ({_level_text(seed, c, t[c])})"
    if t["C1"] == t["C2"] == "full":
        task = (f"Keep the line \"r = ...\" exactly as it is and rewrite only the explanation so that criterion C3 "
                f"(Explanation) earns exactly {lt('C3')}.")
    else:
        expl = {"partial": f"Then write an explanation that earns C3 {lt('C3')}: it explains correctly the direction "
                           "that still holds for the new r, and wrongly claims the other direction also holds.",
                "minimal": "Then write only one short sentence claiming that r works, with no reasoning.",
                "none": "Write no explanation at all: the answer is only the line \"r = ...\"."}[t["C3"]]
        task = ("Write the answer of a student who made a mistake in their regular expression. Change the regular "
                f"expression so that soundness (C1) earns exactly {lt('C1')} and completeness (C2) earns exactly "
                f"{lt('C2')}. {expl} The student believes their answer is correct.")
    return (
        f"Below is an exam question, its grading rubric, and a correct student answer.\n\n{ga.question_and_rubric(seed)}"
        f"\n\nCorrect answer:\n{ref_text}\n\n{task}\n\nKeep the first line in the form \"r = <regular expression>\" "
        "in plain text, as in the correct answer. Do not say or hint that anything is wrong, and do not mention the "
        "rubric, the criteria or marks. Return only the new answer."
    )


def judged_criteria(t: dict) -> list[str]:
    """The regex criteria the level check grades: C1 none (matches every string) and C3 none (no
    explanation) are certain, and so is full; the rest is graded by the teacher."""
    return [c for c in ("C1", "C2", "C3") if t[c] != "full" and not (c in ("C1", "C3") and t[c] == "none")]


def build_regex(teacher, seed: dict, ref: dict, t: dict, cand_id: str, global_seed: int, judge=None):
    """(answer, notes, failure, facts, level_check) for a regex answer with levels t.

    The code checks every rewrite: full soundness or completeness must really hold, a "none"
    soundness must match every string, and anything in between must really fail. Whether a failure
    is "partial" (one kind of wrong string) or "minimal" (several kinds) can't be decided by code,
    so with judge(cid, answer, facts) -> level the teacher grades each of those criteria (and an
    off explanation) blind, given the strings the code found, and the rewrite is kept only if
    every level agrees. level_check lists what the judge said about the rewrites it rejected."""
    lang = regex_language(seed)
    ref_rx = regex_of(ref["text"])
    facts_for = lambda rx: regex_facts(rx, classify(rx, *lang), lang[0])
    if t["C1"] == t["C2"] == t["C3"] == "full":
        return ref["text"], "copied from the reference", "", facts_for(ref_rx), []
    if t["C1"] == t["C2"] == "full" and t["C3"] == "none":
        return f"r = {ref_rx}", "explanation left out", "", facts_for(ref_rx), []
    rejected, judged_off = 0, []
    for attempt in range(5 if judge else 4):
        text = teacher.chat(regex_rewrite_prompt(seed, ref["text"], t), temperature=0.7, max_tokens=900,
                            seed=ga.stable_int(cand_id, "regex", attempt, global_seed)).strip()
        rx = regex_of(text)
        if t["C1"] == t["C2"] == "full" and rx != ref_rx:
            rejected += 1
            continue
        cls = classify(rx, *lang)
        if not regex_ok_for(t, cls):
            rejected += 1
            continue
        if t["C3"] == "none":
            text = f"r = {rx}"
        facts = regex_facts(rx, cls, lang[0])
        if judge:
            judged = judged_criteria(t)
            said = {c: judge(c, text, facts) for c in judged}
            off = [f"{c} {said[c] or 'unclear'}" for c in judged if said[c] != t[c]]
            if off:
                judged_off.append(", ".join(off))
                continue
        how = ("levels confirmed by the teacher's blind level check" if judge else
               "partial vs minimal on C1/C2 and the C3 level are the teacher's: check them")
        return text, (f"checked by code: r = {rx} is sound {cls['sound']}, complete {cls['complete']}, matches "
                      f"everything {cls['everything']} ({rejected} rewrites rejected by the code check, "
                      f"{len(judged_off)} by the level check); {how}."), "", facts, judged_off
    return "", (f"{rejected} rewrites rejected by the code check, {len(judged_off)} by the level check"
                + (f" (the teacher graded them: {'; '.join(judged_off)})" if judged_off else "")), \
        "a regex rewrite failed", "", judged_off


# ============================================================================== shared

def reference_prompt(seed, style):
    return dfa_reference_prompt(seed, style) if seed["topic"] == "dfa_nfa" else regex_reference_prompt(seed, style)


def check_reference(seed, text):
    return check_dfa_reference(seed, text) if seed["topic"] == "dfa_nfa" else check_regex_reference(seed, text)


def plan(seed, refs, n, global_seed):
    return dfa_plan(seed, refs, n, global_seed) if seed["topic"] == "dfa_nfa" else regex_plan(seed, refs, n, global_seed)
