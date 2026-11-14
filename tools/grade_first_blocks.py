"""InstructLab SDG blocks that run the grade-first generator (tools/gen_answers.py) inside
`ilab data generate`.

ilab still does everything around the generation: it reads and validates the taxonomy, sends
each grading skill's seed examples through the pipeline, talks to the teacher at --endpoint-url,
checkpoints, and mixes the results into skills_train_msgs and node_datasets as usual. Only the
grounded-skills pipeline changes: pipelines/grade_first/grounded_skills.yaml runs these blocks
instead of ilab's write-question / write-answer / judge blocks.

The blocks, in pipeline order, are the steps of gen_answers.py, and they call its functions, so
the two can't drift apart:

  GradeFirstSeeds       finds each seed row's question in seeds.json (made by extract_seeds.py)
  GradeFirstReferences  the teacher writes correct reference answers, split per criterion;
                        the code checks c and n_0 or the closed form where it can
  GradeFirstTargets     picks each new answer's grade in advance (make_targets): one row per answer
  GradeFirstAnswers     builds each answer: copies full parts, leaves out or rewrites the off parts
  GradeFirstLabels      the teacher writes the one-sentence reasons; the code writes the levels,
                        points and total, and the training prompt and label

Every block takes `repo` (the repo folder, for tools/extract_seeds.py). The number of answers
per question is `per_question` in GradeFirstTargets; "scaled" means ilab's --sdg-scale-factor.

ilab can't load blocks from a file by itself, so run it through tools/ilab_grade_first.py, which
imports this module (registering the blocks) and then runs the normal ilab command.

Each answer's references, changes and label are also written to
OUTPUT_DIR/grade_first_review/<seed_id>.md for the people checking the data.

The DFA and regex skills (topics dfa_nfa and regex) go through tools/grade_first_formal.py
instead, because every criterion there grades the same machine or expression: the code runs the
DFA or regex, so DFA labels are computed from the answer and regex rewrites are checked on every
string up to length 10.

With `extras: true` (the default in make_grade_first_pipeline.py), the blocks also use
tools/grade_first_extras.py: more parts that may be off (the induction hypothesis), up to three
off at once, whole-answer mistakes whose grade the rubric's general rules fix (a larger c, the
Master Theorem only, a termination argument only, another method, a near-blank answer), and
more reference styles. With `extras: false` they do exactly what gen_answers.py does.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from datasets import Dataset
from instructlab.sdg.blocks.block import Block
from instructlab.sdg.registry import BlockRegistry

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_answers as ga  # noqa: E402
import grade_first_extras as gx  # noqa: E402
import grade_first_formal as fm  # noqa: E402

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_SEEDS: dict[str, dict] = {}  # topic -> {seed_id: seed}
_TOPIC_MARK = "_csc236_"


# ----------------------------------------------------------------------------- seeds


def _abs(pipe, path: str) -> str:
    return (
        path
        if os.path.isabs(path)
        else os.path.normpath(os.path.join(os.path.dirname(pipe.config_path), path))
    )


def topic_of(leaf_node_path: str) -> str:
    """'compositional_skills_grounded_grading_csc236_induction_simple' -> 'induction_simple'."""
    if "grading" not in leaf_node_path or _TOPIC_MARK not in leaf_node_path:
        raise ValueError(
            f"{leaf_node_path} is not a CSC236 grading skill. The grade_first pipeline only "
            "handles compositional_skills/grounded/grading/csc236/<topic>; generate other "
            "skills with another pipeline."
        )
    topic = leaf_node_path.rsplit(_TOPIC_MARK, 1)[1]
    if topic not in ga.SAFE_PARTS and topic not in fm.FORMAL_TOPICS:
        raise ValueError(
            f"gen_answers.py has no SAFE_PARTS list for {topic}, and grade_first_formal.py doesn't "
            "handle it either, so no answers can be made for it."
        )
    return topic


def is_formal(seed: dict) -> bool:
    """DFA and regex answers are built and checked by tools/grade_first_formal.py."""
    return seed["topic"] in fm.FORMAL_TOPICS


def seeds_for(repo: str, topic: str) -> dict:
    """The topic's seeds from tools/extract_seeds.py, read once per run."""
    with _LOCK:
        if topic not in _SEEDS:
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "seeds.json")
                subprocess.run(
                    [
                        sys.executable,
                        os.path.join(repo, "tools", "extract_seeds.py"),
                        repo,
                        out,
                        topic,
                    ],
                    check=True,
                )
                with open(out, encoding="utf-8") as fh:
                    seeds = [s for s in json.load(fh) if s["topic"] == topic]
            if not seeds:
                raise ValueError(f"extract_seeds.py found no seeds for {topic}")
            # As in gen_answers.main: the style example is the next question's seed grade.
            for i, s in enumerate(seeds):
                s["style_example"] = ga.seed_reason_examples(
                    seeds[(i + 1) % len(seeds)]
                )
            _SEEDS[topic] = {s["seed_id"]: s for s in seeds}
        return _SEEDS[topic]


def _norm(text: str) -> str:
    return " ".join(str(text).split())


def match_seed(seeds: dict, row: dict) -> dict:
    """The seed whose question is in this row's seed_context. Two seeds can share a question,
    so the seed's grade (the row's seed_response) decides between them."""
    context = _norm(row.get("seed_context", ""))
    found = [s for s in seeds.values() if _norm(s["question"]) in context]
    if len(found) > 1:
        same_grade = [
            s
            for s in found
            if _norm(s.get("seed_grade", "")) == _norm(row.get("seed_response", ""))
        ]
        found = same_grade or found
    if not found:
        raise ValueError(
            f"no seed in seeds.json matches this question: {context[:150]}"
        )
    return found[0]


def seed_of(repo: str, row: dict) -> dict:
    return seeds_for(repo, row["topic"])[row["seed_id"]]


# ----------------------------------------------------------------------------- teacher and helpers


class Teacher:
    """Chat calls through ilab's own client, with the same settings as gen_answers.Client."""

    def __init__(self, ctx):
        self.ctx = ctx

    def chat(self, user: str, *, temperature: float, max_tokens: int, seed: int) -> str:
        last = None
        for attempt in range(3):
            try:
                r = self.ctx.client.chat.completions.create(
                    model=self.ctx.model_id,
                    temperature=temperature,
                    top_p=0.95,
                    max_tokens=max_tokens,
                    seed=seed,
                    messages=[
                        {"role": "system", "content": ga.GEN_SYSTEM},
                        {"role": "user", "content": user},
                    ],
                    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
                )
                text = r.choices[0].message.content or ""
                return ga.THINK_RE.sub("", text).split("</think>")[-1].strip()
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 + 3 * attempt)
        raise RuntimeError(f"request failed 3 times: {type(last).__name__}: {last}")


def pmap(fn, items, workers):
    """fn over items in a thread pool, results in order; an exception is returned in its place."""

    def safe(item):
        try:
            return fn(item)
        except Exception as exc:  # noqa: BLE001
            logger.warning("grade_first: %s: %s", type(exc).__name__, exc)
            return exc

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(safe, items))


def review_dir(ctx, configured):
    if configured:
        return configured
    if ctx.checkpoint_dir:
        return os.path.join(
            os.path.dirname(os.path.normpath(ctx.checkpoint_dir)), "grade_first_review"
        )
    return os.path.abspath("grade_first_review")


def append_review(folder: str, seed_id: str, lines: list[str]) -> None:
    with _LOCK:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"{seed_id}.md"), "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")


def empty_like(samples):
    return samples.select([])


# ----------------------------------------------------------------------------- blocks


@BlockRegistry.register("GradeFirstSeeds")
class GradeFirstSeeds(Block):
    """Adds topic and seed_id to each seed row."""

    def __init__(self, ctx, pipe, block_name, repo):
        super().__init__(ctx, pipe, block_name)
        self.repo = _abs(pipe, repo)

    def generate(self, samples):
        rows = samples.to_list()
        for r in rows:
            r["topic"] = topic_of(r["leaf_node_path"])
            r["seed_id"] = match_seed(seeds_for(self.repo, r["topic"]), r)["seed_id"]
        logger.info("grade_first: %d seed questions", len(rows))
        return Dataset.from_list(rows)


@BlockRegistry.register("GradeFirstReferences")
class GradeFirstReferences(Block):
    """The teacher writes `refs` correct answers per question (step 1 of gen_answers.py)."""

    def __init__(
        self,
        ctx,
        pipe,
        block_name,
        repo,
        refs=3,
        workers=32,
        seed=0,
        temperature=0.8,
        max_tokens=2000,
        review=None,
        extras=False,
    ):
        super().__init__(ctx, pipe, block_name)
        self.repo, self.refs, self.workers, self.seed = (
            _abs(pipe, repo),
            int(refs),
            int(workers),
            int(seed),
        )
        self.temperature, self.max_tokens = float(temperature), int(max_tokens)
        self.review = review_dir(ctx, review)
        self.extras = bool(extras)

    def generate(self, samples):
        rows = samples.to_list()
        teacher = Teacher(self.ctx)
        jobs = [(i, k) for i in range(len(rows)) for k in range(self.refs)]

        def make_ref(job):
            i, k = job
            s = seed_of(self.repo, rows[i])
            ids = [c["id"] for c in s["criteria"]]
            style = (
                gx.style_for(s["seed_id"], k)
                if self.extras or is_formal(s)
                else ga.STYLES[k % len(ga.STYLES)]
            )
            if is_formal(s):  # one whole answer, checked by running the DFA or regex
                for attempt in range(3):
                    raw = teacher.chat(
                        fm.reference_prompt(s, style),
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        seed=ga.stable_int(s["seed_id"], k, attempt, self.seed),
                    ).strip()
                    check = fm.check_reference(s, raw)
                    if check["result"] == "right" or attempt == 2:
                        return {
                            "ref_id": f"{s['seed_id']}_r{k + 1}",
                            "seed_id": s["seed_id"],
                            "style": style,
                            "text": raw,
                            "parts": {"answer": raw},
                            "attempts": attempt + 1,
                            "code_check": check
                            if check["result"] == "right"
                            else {**check, "result": "wrong"},
                        }
                return None
            for attempt in range(3):
                raw = teacher.chat(
                    ga.reference_prompt(s, style),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    seed=ga.stable_int(s["seed_id"], k, attempt, self.seed),
                )
                parts = ga.split_parts(raw, ids)
                if parts:
                    ref = {
                        "ref_id": f"{s['seed_id']}_r{k + 1}",
                        "seed_id": s["seed_id"],
                        "style": style,
                        "parts": parts,
                        "attempts": attempt + 1,
                    }
                    ref["code_check"] = ga.check_reference(s, ref)
                    return ref
            return None

        results = pmap(make_ref, jobs, self.workers)
        out = []
        for i, r in enumerate(rows):
            s = seed_of(self.repo, r)
            mine = [
                x for (j, _), x in zip(jobs, results) if j == i and isinstance(x, dict)
            ]
            usable = [x for x in mine if x["code_check"]["result"] != "wrong"]
            lines = [
                f"# {s['seed_id']}",
                "",
                "**Question:** " + s["question"].replace("\n", " "),
                "",
            ]
            for ref in mine:
                chk = ref["code_check"]
                note = (
                    f" (code check: {chk['result']}, {chk['note']})"
                    if chk["result"] != "not checked"
                    else ""
                )
                lines += [
                    f"## Reference {ref['ref_id']}{note}"
                    + ("  DROPPED" if ref not in usable else ""),
                    "",
                ]
                for cid, text in ref["parts"].items():
                    lines += [f"**{cid}**", "", "```", text, "```", ""]
            append_review(self.review, s["seed_id"], lines)
            logger.info(
                "grade_first: %s: %d of %d references usable",
                s["seed_id"],
                len(usable),
                self.refs,
            )
            if usable:
                r["refs_json"] = json.dumps(usable, ensure_ascii=False)
                out.append(r)
        return Dataset.from_list(out) if out else empty_like(samples)


@BlockRegistry.register("GradeFirstTargets")
class GradeFirstTargets(Block):
    """Picks the grade of every new answer before it is written (step 2): one row per answer."""

    def __init__(
        self, ctx, pipe, block_name, repo, per_question="scaled", seed=0, extras=False
    ):
        super().__init__(ctx, pipe, block_name)
        self.repo, self.seed, self.extras = _abs(pipe, repo), int(seed), bool(extras)
        if per_question == "scaled":
            per_question = ctx.num_instructions_to_generate or 13
        self.per_question = int(per_question)

    def generate(self, samples):
        out = []
        for r in samples.to_list():
            s = seed_of(self.repo, r)
            refs = json.loads(r["refs_json"])
            by_id = {x["ref_id"]: x for x in refs}
            base = {k: v for k, v in r.items() if k != "refs_json"}
            if is_formal(s):
                planned = fm.plan(s, refs, self.per_question, self.seed)
            elif self.extras:
                planned = gx.plan(s, refs, self.per_question, self.seed)
            else:
                planned = [
                    {**t, "scenario": ""}
                    for t in ga.make_targets(s, refs, self.per_question, self.seed)
                ]
            for i, t in enumerate(planned):
                out.append(
                    {
                        **base,
                        "cand_id": f"{s['seed_id']}_a{i + 1:02d}",
                        "ref_json": json.dumps(by_id[t["ref_id"]], ensure_ascii=False),
                        "target_json": json.dumps(t["target"]),
                        "scenario": t["scenario"],
                        "prebuilt": t.get("prebuilt", ""),
                        "check": t.get("check", ""),
                        "trick": t["trick"] or "",
                        "trick_at_start": bool(t["trick_at_start"]),
                    }
                )
        logger.info("grade_first: %d answers planned", len(out))
        return Dataset.from_list(out) if out else empty_like(samples)


@BlockRegistry.register("GradeFirstAnswers")
class GradeFirstAnswers(Block):
    """Builds each answer from its reference (step 3): full parts are copied, a missing-part
    'none' is left out, and every other off part is rewritten by the teacher to its level."""

    def __init__(
        self,
        ctx,
        pipe,
        block_name,
        repo,
        workers=32,
        seed=0,
        temperature=0.6,
        max_tokens=1200,
        extras=False,
    ):
        super().__init__(ctx, pipe, block_name)
        self.repo, self.workers, self.seed = _abs(pipe, repo), int(workers), int(seed)
        self.temperature, self.max_tokens = float(temperature), int(max_tokens)
        self.extras = bool(extras)

    def _with_trick(self, r, answer):
        if r["trick"]:
            return (
                f"{r['trick']}\n\n{answer}"
                if r["trick_at_start"]
                else f"{answer}\n\n{r['trick']}"
            )
        return answer

    def _scenario(self, teacher, r, s, ref):
        """A whole-answer mistake whose levels the rubric's general rule fixes (grade_first_extras)."""
        sc = next((x for x in gx.scenarios_for(s) if x["name"] == r["scenario"]), None)
        if sc is None:
            return "", [], f"unknown scenario {r['scenario']}"
        first, rejected = list(ref["parts"])[0], 0
        for attempt in range(3):
            text = ga.clean_part(
                teacher.chat(
                    gx.scenario_prompt(s, ref["parts"], sc),
                    temperature=0.7,
                    max_tokens=1500,
                    seed=ga.stable_int(r["cand_id"], "scenario", attempt, self.seed),
                )
            )
            if not text or "<<" in text:
                continue
            if not sc["check"](text):
                rejected += 1
                continue
            answer = (
                f"{ref['parts'][first].strip()}\n\n{text}" if sc["keep_first"] else text
            )
            change = {
                "criterion": "all",
                "level": "scenario",
                "method": f"scenario {sc['name']}",
                "text": text,
                "mistake": sc["instruction"],
                "rejected_by_check": rejected,
            }
            return self._with_trick(r, answer), [change], ""
        return (
            "",
            [
                {
                    "criterion": "all",
                    "level": "scenario",
                    "method": f"scenario {sc['name']}",
                    "text": None,
                    "rejected_by_check": rejected,
                }
            ],
            "a scenario rewrite failed",
        )

    def generate(self, samples):
        rows = samples.to_list()
        teacher = Teacher(self.ctx)

        def build(r):
            s = seed_of(self.repo, r)
            ref, target = json.loads(r["ref_json"]), json.loads(r["target_json"])
            if is_formal(s):
                if (
                    s["topic"] == "dfa_nfa"
                ):  # built and graded by code in GradeFirstTargets
                    change = {
                        "criterion": "all",
                        "level": "code",
                        "method": "built and graded by code",
                        "text": r["prebuilt"],
                        "mistake": r["check"],
                    }
                    return self._with_trick(r, r["prebuilt"]), [change], ""
                answer, notes, failed = fm.build_regex(
                    teacher, s, ref, target, r["cand_id"], self.seed
                )
                change = {
                    "criterion": "all",
                    "level": "regex",
                    "method": "regex",
                    "text": answer,
                    "mistake": notes,
                }
                return (self._with_trick(r, answer) if answer else ""), [change], failed
            if r.get("scenario"):
                return self._scenario(teacher, r, s, ref)
            safe = gx.safe_parts_plus(s, ref) if self.extras else ga.safe_parts(s, ref)
            parts, changes = dict(ref["parts"]), []
            for crit in s["criteria"]:
                lv = target[crit["id"]]
                if lv == "full":
                    continue
                if lv not in safe.get(crit["id"], {}):
                    raise RuntimeError(
                        f"{r['cand_id']}: {crit['id']} {lv} is not in SAFE_PARTS"
                    )
                mistake = safe[crit["id"]][lv]
                none_text = (
                    crit["levels"]["none"]["text"] if "none" in crit["levels"] else ""
                )
                if lv == "none" and mistake is None and ga.MISSING_RE.search(none_text):
                    # A "none" that also names a wrong alternative is written as that mistake half the time.
                    alt = gx.none_alternative(none_text) if self.extras else None
                    if (
                        alt
                        and ga.stable_int(r["cand_id"], crit["id"], "alternative") % 2
                        == 0
                    ):
                        mistake = alt
                    else:
                        parts[crit["id"]] = ""
                        changes.append(
                            {
                                "criterion": crit["id"],
                                "level": lv,
                                "method": "left out",
                                "text": "",
                            }
                        )
                        continue
                text, still_right = None, 0
                for attempt in range(3):
                    new = ga.clean_part(
                        teacher.chat(
                            ga.rewrite_prompt(s, ref["parts"], crit, lv, mistake),
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            seed=ga.stable_int(
                                r["cand_id"], crit["id"], attempt, self.seed
                            ),
                        )
                    )
                    if (
                        not new
                        or new.strip() == ref["parts"][crit["id"]].strip()
                        or "<<" in new
                    ):
                        continue
                    if ga.rewrite_still_right(s, crit["id"], new):
                        still_right += 1
                        continue
                    text = new
                    break
                changes.append(
                    {
                        "criterion": crit["id"],
                        "level": lv,
                        "method": "rewritten",
                        "text": text,
                        "mistake": mistake,
                        "still_right": still_right,
                    }
                )
                if text is None:
                    return "", changes, "a rewrite failed"
                parts[crit["id"]] = text
            answer = "\n\n".join(p.strip() for p in parts.values() if p and p.strip())
            return self._with_trick(r, answer), changes, ""

        built = pmap(build, rows, self.workers)
        for r, b in zip(rows, built):
            if isinstance(b, Exception):
                b = ("", [], f"{type(b).__name__}: {b}")
            r["answer"], r["changes_json"], r["failed"] = (
                b[0],
                json.dumps(b[1], ensure_ascii=False),
                b[2],
            )
        logger.info(
            "grade_first: %d answers built, %d failed",
            sum(not r["failed"] for r in rows),
            sum(bool(r["failed"]) for r in rows),
        )
        return Dataset.from_list(rows) if rows else empty_like(samples)


@BlockRegistry.register("GradeFirstLabels")
class GradeFirstLabels(Block):
    """The teacher writes the reasons for the levels it is given; the code writes the label (steps 4-5).
    Sets `question` (the grading prompt with the answer) and `response` (the label), the two
    columns ilab turns into the training messages."""

    def __init__(
        self,
        ctx,
        pipe,
        block_name,
        repo,
        workers=32,
        seed=0,
        temperature=0.2,
        max_tokens=700,
        review=None,
    ):
        super().__init__(ctx, pipe, block_name)
        self.repo, self.workers, self.seed = _abs(pipe, repo), int(workers), int(seed)
        self.temperature, self.max_tokens = float(temperature), int(max_tokens)
        self.review = review_dir(ctx, review)

    def generate(self, samples):
        rows = samples.to_list()
        teacher = Teacher(self.ctx)

        def reasons(r):
            if r["failed"]:
                return {}
            s = seed_of(self.repo, r)
            text = teacher.chat(
                ga.reasons_prompt(s, r["answer"], json.loads(r["target_json"])),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                seed=ga.stable_int(r["cand_id"], "reasons", self.seed),
            )
            return ga.parse_reasons(text, [c["id"] for c in s["criteria"]])

        found = pmap(reasons, rows, self.workers)
        fallbacks = 0
        for r, rs in zip(rows, found):
            r["question"], r["response"] = "", ""
            if r["failed"]:
                continue
            s = seed_of(self.repo, r)
            target = json.loads(r["target_json"])
            rs = rs if isinstance(rs, dict) else {}
            reasons_by_id = {}
            for crit in s["criteria"]:
                if crit["id"] in rs:
                    reasons_by_id[crit["id"]] = rs[crit["id"]]
                else:
                    reasons_by_id[crit["id"]] = ga.fallback_reason(
                        crit, target[crit["id"]]
                    )
                    fallbacks += 1
            label, _, _ = ga.training_label(s, target, reasons_by_id)
            r["question"] = s["context"] + "\n\nStudent Answer:\n" + r["answer"]
            r["response"] = label
            self._review(s, r, label)
        logger.info(
            "grade_first: %d labels written, %d reasons taken from the rubric",
            sum(bool(r["response"]) for r in rows),
            fallbacks,
        )
        return Dataset.from_list(rows) if rows else empty_like(samples)

    def _review(self, s, r, label):
        target = json.loads(r["target_json"])
        tgt = ", ".join(f"{k} {v}" for k, v in target.items())
        lines = [
            f"## Answer {r['cand_id']} (built on {json.loads(r['ref_json'])['ref_id']}): {tgt}"
            + (f" [scenario: {r['scenario']}]" if r.get("scenario") else "")
            + (" [trick]" if r["trick"] else ""),
            "",
        ]
        changes = json.loads(r["changes_json"])
        for ch in changes:
            if ch["criterion"] == "all":
                lines.append(
                    f"- **Whole answer** ({ch['method']}): {ch.get('mistake', '')}"
                )
                continue
            crit = next(c for c in s["criteria"] if c["id"] == ch["criterion"])
            only = f" Only this kind: {ch['mistake']}" if ch.get("mistake") else ""
            lines.append(
                f"- **{ch['criterion']} {ch['level']}** ({ch['method']}). "
                f"Rubric: {crit['levels'][ch['level']]['text']}{only}"
            )
        if not changes:
            lines.append("- All full: copied from the reference unchanged.")
        lines += [
            "",
            "Whole answer:",
            "",
            "```",
            r["answer"],
            "```",
            "",
            "Grade as it will be trained:",
            "",
            "```",
            label,
            "```",
            "",
        ]
        append_review(self.review, s["seed_id"], lines)
