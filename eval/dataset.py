"""Load the test set read-only, check it, and choose the cases for a run.

The file is identified by its SHA-256 hash, not its name. The repo's test_set/groupB_60_draft.json
holds Group B draft v3, although v2 had the same file name, and its version field did not change
when grading_policies[1] was shortened on 2026-10-30. Loading stops if the hash is not the one
expected.

Nothing here writes to the test set or changes its labels. check_structure only reports problems;
it never fixes them.

Filters choose the cases a run is about (role "selected"). A selected paraphrase, fairness,
sensitivity or robustness case needs its parent's grade for comparison, so a parent that the filters
did not choose is added with role "context_parent". It is graded, but used only as the reference
side of those comparisons, never in counts or metric denominators.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO / "test_set" / "groupB_60_draft.json"
# Group B draft v3 (version "draft-v3-2026-10-29"), human-reviewed. It differs from the original v3
# file, whose hash was ca2ef30d576f5e44f1ed321540f48dcad6e0b49d39d091d09af7396df939c423: on 2026-10-30
# grading_policies[1] was cut back to its general principle (the rubrics already state the removed
# parts), and in 2026-11 Q08's C2 minimal and none levels and the C1 justification of ans02 and
# ans02_kw1 were reworded and the review metadata was updated. No score or level changed.
EXPECTED_SHA256 = "ecd69def58cf75b87032ef96419767e008e7481150170839411b47e8f1011cbc"

LEVELS = ("full", "partial", "minimal", "none")
TEST_TYPES = ("original", "paraphrase", "fairness", "sensitivity", "robustness")
# The prompt builder knows how to render exactly these fields.
GRADER_VISIBLE = ("question", "rubric", "student_answer")
TEST_ID_RE = re.compile(r"^csc236_B_[a-z]+_[0-9]{2}_ans[0-9]{2}(_(para|fair|sens|inj|kw)[0-9])?$")
MARKS_RE = re.compile(r"\[(\d+) marks\]\s*$")
IDENTICAL_TYPES = ("paraphrase", "fairness", "robustness")

SELECTED = "selected"
CONTEXT_PARENT = "context_parent"


class DatasetError(Exception):
    pass


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@dataclass(frozen=True)
class Dataset:
    path: Path
    sha256: str
    data: dict

    @property
    def cases(self) -> list[dict]:
        return self.data["test_cases"]

    @property
    def version(self) -> str:
        return self.data.get("version", "")

    @property
    def status(self) -> str:
        return self.data.get("status", "")

    @property
    def grader_visible_fields(self) -> list[str]:
        return list(self.data["grader_visible_fields"])

    @property
    def held_out_fields(self) -> list[str]:
        return list(self.data["held_out_fields"])

    @property
    def grading_policies(self) -> list[str]:
        return list(self.data["grading_policies"])

    def by_id(self) -> dict[str, dict]:
        return {c["test_id"]: c for c in self.cases}

    def describe(self) -> dict:
        """What a run config records about the dataset."""
        return {"path": str(self.path), "sha256": self.sha256, "version": self.version,
                "status": self.status, "case_count": len(self.cases)}


def load(path=DEFAULT_DATASET, expected_sha256: str | None = EXPECTED_SHA256) -> Dataset:
    """Read the file once, check its hash, then parse those same bytes.

    Pass expected_sha256=None only on purpose, e.g. to inspect another version.
    """
    path = Path(path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise DatasetError(f"{path} has SHA-256 {digest}, expected {expected_sha256}. "
                           "This is not the dataset version this run expects.")
    data = json.loads(raw.decode("utf-8"))
    if data.get("grader_visible_fields") != list(GRADER_VISIBLE):
        raise DatasetError(f"grader_visible_fields is {data.get('grader_visible_fields')}; the prompt "
                           f"builder supports exactly {list(GRADER_VISIBLE)}")
    return Dataset(path=path, sha256=digest, data=data)


def verify_unchanged(ds: Dataset) -> None:
    """Raise if the file on disk no longer has the hash it had when it was loaded."""
    now = sha256_file(ds.path)
    if now != ds.sha256:
        raise DatasetError(f"{ds.path} changed during the run: SHA-256 {ds.sha256} -> {now}")


def grader_input(case: dict) -> dict:
    """The only fields of a case the model may see."""
    return {field: case[field] for field in GRADER_VISIBLE}


def gold_criteria(case: dict) -> dict[str, dict]:
    """Draft per-criterion labels: {criterion_id: {level, score, max}}. Provisional."""
    maxima = {c["id"]: c["max"] for c in case["rubric"]}
    return {g["criterion_id"]: {"level": g["level"], "score": g["score"], "max": maxima[g["criterion_id"]]}
            for g in case["draft_ground_truth"]["criteria"]}


# --------------------------------------------------------------------------- checks

def _rubric_problems(case: dict) -> list[str]:
    problems, seen = [], set()
    for c in case["rubric"]:
        cid = c.get("id")
        if cid in seen:
            problems.append(f"{cid} appears twice in the rubric")
        seen.add(cid)
        levels = c.get("levels") or {}
        if tuple(levels) != LEVELS:
            problems.append(f"{cid} levels are {list(levels)}, expected {list(LEVELS)}")
            continue
        pts = [levels[name]["points"] for name in LEVELS]
        if pts[0] != c["max"]:
            problems.append(f"{cid} full is {pts[0]} points but max is {c['max']}")
        if pts[-1] != 0:
            problems.append(f"{cid} none is {pts[-1]} points, expected 0")
        if any(a <= b for a, b in zip(pts, pts[1:])):
            problems.append(f"{cid} level points do not strictly decrease: {pts}")
    total = sum(c["max"] for c in case["rubric"])
    m = MARKS_RE.search(case["question"])
    if not m:
        problems.append("question does not end with [N marks]")
    elif int(m.group(1)) != total:
        problems.append(f"question says [{m.group(1)} marks] but the rubric maxima sum to {total}")
    return problems


def _label_problems(case: dict) -> list[str]:
    problems = []
    rubric = {c["id"]: c for c in case["rubric"]}
    gt = case["draft_ground_truth"]
    ids = [g["criterion_id"] for g in gt["criteria"]]
    if ids != list(rubric):
        problems.append(f"draft_ground_truth criteria {ids} do not match the rubric {list(rubric)}")
        return problems
    for g in gt["criteria"]:
        if g["level"] not in LEVELS:
            problems.append(f"{g['criterion_id']} level {g['level']!r} is not a rubric level")
        elif rubric[g["criterion_id"]]["levels"][g["level"]]["points"] != g["score"]:
            problems.append(f"{g['criterion_id']} {g['level']} is not worth {g['score']} points")
    if sum(g["score"] for g in gt["criteria"]) != gt["total_score"]:
        problems.append("criterion scores do not sum to total_score")
    if gt["max_score"] != sum(c["max"] for c in case["rubric"]):
        problems.append("max_score does not equal the sum of the rubric maxima")
    if case["ta_score"] != gt["total_score"]:
        problems.append("ta_score does not equal draft_ground_truth.total_score")
    if case["ta_criteria"] != {g["criterion_id"]: g["score"] for g in gt["criteria"]}:
        problems.append("ta_criteria does not equal the draft_ground_truth scores")
    return problems


def _relation_problems(case: dict, cases: dict[str, dict]) -> list[str]:
    problems = []
    relation = case["expected_relation_to_parent"]
    parent_id = case["parent_test_id"]
    if case["test_type"] == "original":
        if parent_id is not None or relation is not None:
            problems.append("an original should have no parent and no relation")
        return problems
    parent = cases.get(parent_id)
    if parent is None:
        return [f"parent_test_id {parent_id!r} is not in the dataset"]
    if parent["question_id"] != case["question_id"]:
        problems.append("parent has a different question_id")
    try:
        mine, theirs = gold_criteria(case), gold_criteria(parent)
    except KeyError as exc:  # a broken rubric, reported by the rubric checks
        return problems + [f"labels can't be compared with the parent's: criterion {exc} is not in a rubric"]
    kind = (relation or {}).get("relation")
    if case["test_type"] in IDENTICAL_TYPES:
        if kind != "identical_to_parent":
            problems.append(f"{case['test_type']} case has relation {kind!r}, expected identical_to_parent")
        elif mine != theirs:
            problems.append("labels differ from the parent although the relation is identical_to_parent")
    elif case["test_type"] == "sensitivity":
        if kind != "lower_than_parent":
            return problems + [f"sensitivity case has relation {kind!r}, expected lower_than_parent"]
        diffs = {cid: mine[cid]["score"] - theirs[cid]["score"]
                 for cid in mine if mine[cid]["score"] != theirs[cid]["score"]}
        if diffs != relation.get("criteria_changes"):
            problems.append(f"criteria_changes {relation.get('criteria_changes')} != label differences {diffs}")
        if relation.get("total_change") != sum(diffs.values()):
            problems.append("total_change does not equal the sum of the criterion changes")
        if not diffs or any(d >= 0 for d in diffs.values()):
            problems.append("a sensitivity case should score lower than its parent")
    return problems


def check_structure(ds: Dataset) -> list[str]:
    """Problems found in the dataset, as 'test_id: message' strings. Empty means none."""
    problems = []
    data = ds.data
    if data.get("case_count") != len(ds.cases):
        problems.append(f"case_count is {data.get('case_count')} but there are {len(ds.cases)} cases")
    expected_keys = set(data["grader_visible_fields"]) | set(data["held_out_fields"])
    ids = [c.get("test_id") for c in ds.cases]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"{dup}: test_id appears more than once")
    cases = ds.by_id()
    groups: dict[str, list[dict]] = {}
    for case in ds.cases:
        tid = case.get("test_id")
        keys = set(case)
        here = []
        if keys != expected_keys:
            here.append(f"fields missing {sorted(expected_keys - keys)}, unexpected {sorted(keys - expected_keys)}")
            problems += [f"{tid}: {p}" for p in here]
            continue
        if not TEST_ID_RE.match(tid):
            here.append("test_id does not match the naming pattern")
        if case["test_type"] not in TEST_TYPES:
            here.append(f"unknown test_type {case['test_type']!r}")
        here += _rubric_problems(case)
        here += _label_problems(case)
        here += _relation_problems(case, cases)
        if case["paraphrase_group"]:
            groups.setdefault(case["paraphrase_group"], []).append(case)
        problems += [f"{tid}: {p}" for p in here]
    for name, members in sorted(groups.items()):
        if len({m["question_id"] for m in members}) != 1:
            problems.append(f"paraphrase group {name}: members have different question_ids")
        if sum(m["test_type"] == "original" for m in members) != 1:
            problems.append(f"paraphrase group {name}: expected exactly one original")
    return problems


# --------------------------------------------------------------------------- selection

@dataclass(frozen=True)
class SelectedCase:
    case: dict
    role: str  # SELECTED or CONTEXT_PARENT

    @property
    def test_id(self) -> str:
        return self.case["test_id"]


@dataclass(frozen=True)
class Selection:
    items: tuple[SelectedCase, ...]
    filters: dict

    @property
    def selected(self) -> list[dict]:
        return [i.case for i in self.items if i.role == SELECTED]

    @property
    def selected_ids(self) -> list[str]:
        return [i.test_id for i in self.items if i.role == SELECTED]

    @property
    def context_parent_ids(self) -> list[str]:
        return [i.test_id for i in self.items if i.role == CONTEXT_PARENT]

    def role(self, test_id: str) -> str | None:
        return next((i.role for i in self.items if i.test_id == test_id), None)

    def describe(self) -> dict:
        """What a run config records about the selection."""
        return {"filters": self.filters,
                "selected_count": len(self.selected_ids), "selected_case_ids": self.selected_ids,
                "context_parent_count": len(self.context_parent_ids),
                "context_parent_ids": self.context_parent_ids}

    def headline(self) -> str:
        n, extra = len(self.selected_ids), len(self.context_parent_ids)
        text = f"{n} selected"
        if extra:
            text += f" (+{extra} context parent{'s' if extra != 1 else ''} run for reference)"
        return text


def _check_values(name: str, wanted, allowed) -> list[str]:
    wanted = list(wanted or [])
    unknown = [w for w in wanted if w not in allowed]
    if unknown:
        raise DatasetError(f"unknown {name} {unknown}; choose from {sorted(allowed)}")
    return wanted


def select(ds: Dataset, test_types=None, topics=None, question_ids=None) -> Selection:
    """Cases matching every given filter (each filter matches any of its values).

    No filters selects every case. Parents of selected variants are added as context parents, and
    a case is listed once, in dataset order.
    """
    cases = ds.cases
    test_types = _check_values("test type", test_types, set(TEST_TYPES))
    topics = _check_values("topic", topics, {c["topic"] for c in cases})
    question_ids = _check_values("question id", question_ids, {c["question_id"] for c in cases})

    def matches(c):
        return ((not test_types or c["test_type"] in test_types)
                and (not topics or c["topic"] in topics)
                and (not question_ids or c["question_id"] in question_ids))

    chosen = {c["test_id"] for c in cases if matches(c)}
    by_id = ds.by_id()
    parents = set()
    for tid in chosen:
        parent = by_id[tid]["parent_test_id"]
        while parent is not None and parent not in chosen and parent not in parents:
            parents.add(parent)
            parent = by_id[parent]["parent_test_id"]
    items = tuple(SelectedCase(c, SELECTED if c["test_id"] in chosen else CONTEXT_PARENT)
                  for c in cases if c["test_id"] in chosen or c["test_id"] in parents)
    filters = {"test_type": test_types, "topic": topics, "question_id": question_ids}
    return Selection(items=items, filters=filters)
