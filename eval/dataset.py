"""Load the test set read-only, check it, and choose the cases for a run.

Two test sets are supported, told apart by their cases' `group` field:
- Group B (the default; its default file is v4, test_set/groupB_v4_101.json, and v3 is
  test_set/groupB_60_draft.json): the model sees question, rubric and student_answer, and the
  general rules are the dataset-level `grading_policies`, the same for every case.
- Group A (test_set/groupA_40_final.json): the model also sees each case's own `general_rules`,
  the question-specific rules of the training seed the question comes from. There is no
  dataset-level `grading_policies`.

The file is identified by its SHA-256 hash, not its name. The repo's test_set/groupB_60_draft.json
holds Group B draft v3, although v2 had the same file name, and its version field did not change
when grading_policies[1] was shortened on 2026-10-30. Loading stops if the hash is not the one
expected. Since 2026-11-19 the Group B default is v4 (test_set/groupB_v4_101.json, 101 cases: the 60
v3 cases plus 41). v3 is still supported when chosen with --dataset test_set/groupB_60_draft.json;
both hashes are pinned in PINNED_SHA256. A finished run is re-scored against the file and hash in its
own config, whatever the default.

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
GROUP_B_V3_DATASET = REPO / "test_set" / "groupB_60_draft.json"
# Group B draft v3 (version "draft-v3-2026-10-29"), human-reviewed. It differs from the original v3
# file, whose hash was ca2ef30d576f5e44f1ed321540f48dcad6e0b49d39d091d09af7396df939c423: on 2026-10-30
# grading_policies[1] was cut back to its general principle (the rubrics already state the removed
# parts), and in 2026-11 Q08's C2 minimal and none levels and the C1 justification of ans02 and
# ans02_kw1 were reworded and the review metadata was updated. No score or level changed.
# The Group B default until 2026-11-19; choose it with --dataset (DATASET for the job).
GROUP_B_V3_SHA256 = "ecd69def58cf75b87032ef96419767e008e7481150170839411b47e8f1011cbc"

GROUP_B_V4_DATASET = REPO / "test_set" / "groupB_v4_101.json"
# Group B v4 ("v4-2026-11-19"), 101 cases: the 60 v3 cases with questions, answers and labels unchanged,
# plus 41 cases that are AI-drafted and AI-reviewed, not independently verified by a human; not frozen. It
# has no review_status field (each case's label_source records how its labels were produced). The Group B
# default since 2026-11-19.
GROUP_B_V4_SHA256 = "24d7f3bf5d2862641871796f6b16b4e672d4c2ea97e5176bbbaf2ade082ed4ca"

# The Group B default test set: v4.
DEFAULT_DATASET = GROUP_B_V4_DATASET
EXPECTED_SHA256 = GROUP_B_V4_SHA256
GROUP_B_V4_LABELS_NOTE = ("Scored against Group B v4 labels: AI-drafted; the 60 cases are carried over unchanged "
                          "from v3, and the 41 cases added in v4 are AI-reviewed, not independently verified by a "
                          "human. Provisional, not TA-verified or frozen. Not answer-key results.")

GROUP_A_DATASET = REPO / "test_set" / "groupA_40_final.json"
# Group A final v1 ("final-v1-2026-11-16"), 40 originals. Labels are teacher-model generated, checked
# in an AI-assisted audit, with human decisions on 4 cases; not human-verified end to end, not frozen.
GROUP_A_SHA256 = "226fb91602ed06d3192b495a4ab2085553e3ee41fa1745c3337de4f0dcab81cc"

LEVELS = ("full", "partial", "minimal", "none")
TEST_TYPES = ("original", "paraphrase", "fairness", "sensitivity", "robustness")
# The prompt builder renders exactly these fields of a case; the general rules are passed apart.
GRADER_VISIBLE = ("question", "rubric", "student_answer")
TEST_ID_RE = re.compile(r"^csc236_B_[a-z]+_[0-9]{2}_ans[0-9]{2}(_(para|fair|sens|inj|kw)[0-9])?$")
TEST_ID_RE_A = re.compile(r"^csc236_A_[a-z]+(_[a-z]+)*_[0-9]{2}_a[0-9]{2}$")
RULES_DATASET = "dataset grading_policies"
RULES_CASE = "case general_rules"


@dataclass(frozen=True)
class Group:
    """What differs between the supported test sets."""
    name: str
    grader_visible: tuple[str, ...]   # the dataset's grader_visible_fields, exactly
    rules_source: str                 # RULES_DATASET or RULES_CASE
    test_id_re: re.Pattern
    default_path: Path
    default_sha256: str
    labels_note: str                  # what the labels are, for run configs and summaries


GROUPS = {
    # Group B's labels_note describes v3 and is kept for v3 runs and for configs whose file has no note of
    # its own in LABELS_NOTES (older Group B configs). The default, v4, has its own note there.
    "B": Group("B", GRADER_VISIBLE, RULES_DATASET, TEST_ID_RE, DEFAULT_DATASET, EXPECTED_SHA256,
               "Scored against Group B AI-drafted labels, human-reviewed; provisional and not independently "
               "TA-verified or frozen. Not answer-key results."),
    "A": Group("A", ("question", "rubric", "general_rules", "student_answer"), RULES_CASE, TEST_ID_RE_A,
               GROUP_A_DATASET, GROUP_A_SHA256,
               "Scored against Group A labels: teacher-model generated, checked in an AI-assisted mathematical "
               "audit, with human decisions on 4 cases; not independently human-verified or frozen. Not "
               "answer-key results."),
}
# Pinned test-set files: file -> SHA-256, used when the file is chosen with --dataset and no hash is
# given (a group's default file is also checked against its group's hash).
PINNED_SHA256 = {GROUP_B_V3_DATASET: GROUP_B_V3_SHA256, GROUP_B_V4_DATASET: GROUP_B_V4_SHA256}
# Labels notes that depend on the file, not only on the group: SHA-256 -> note.
LABELS_NOTES = {GROUP_B_V4_SHA256: GROUP_B_V4_LABELS_NOTE}
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
        """Group B's dataset-level rules. Group A has none: use general_rules(case)."""
        return list(self.data["grading_policies"])

    @property
    def group(self) -> Group:
        return GROUPS[group_name(self.data)]

    def general_rules(self, case: dict) -> list[str]:
        """The general rules shown in this case's prompt."""
        if self.group.rules_source == RULES_CASE:
            return list(case["general_rules"])
        return self.grading_policies

    def by_id(self) -> dict[str, dict]:
        return {c["test_id"]: c for c in self.cases}

    def describe(self) -> dict:
        """What a run config records about the dataset."""
        info = {"path": str(self.path), "sha256": self.sha256, "version": self.version,
                "status": self.status, "case_count": len(self.cases)}
        if self.group.name != "B":  # Group B configs stay as they were; a config without it is Group B
            info["group"] = self.group.name
        return info


def group_name(data: dict) -> str:
    """The test set's group, from its cases' `group` field. Raises if it is missing, mixed or unknown."""
    names = {c.get("group") for c in data.get("test_cases") or []}
    if len(names) != 1:
        raise DatasetError(f"the cases' group fields are {sorted(map(str, names))}; expected one group")
    name = names.pop()
    if name not in GROUPS:
        raise DatasetError(f"unknown test-set group {name!r}; supported: {sorted(GROUPS)}")
    return name


def labels_note(config_dataset: dict) -> str:
    """The labels note for a run config's `dataset` entry: the file's own note if it has one (by SHA-256),
    otherwise its group's (no `group` key means Group B)."""
    return LABELS_NOTES.get(config_dataset.get("sha256")) or GROUPS[config_dataset.get("group", "B")].labels_note


def default_sha256(group: Group, path=None) -> str:
    """The hash a file must have when none is given: a pinned file's own, otherwise the group's."""
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        for pinned, sha in PINNED_SHA256.items():
            if resolved == pinned.resolve():
                return sha
    return group.default_sha256


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
    group = GROUPS[group_name(data)]
    if data.get("grader_visible_fields") != list(group.grader_visible):
        raise DatasetError(f"grader_visible_fields is {data.get('grader_visible_fields')}; for Group {group.name} "
                           f"the prompt builder supports exactly {list(group.grader_visible)}")
    if group.rules_source == RULES_DATASET and not _rules_ok(data.get("grading_policies")):
        raise DatasetError("Group B needs a non-empty list of text grading_policies")
    if group.rules_source == RULES_CASE:
        bad = [c.get("test_id") for c in data["test_cases"] if not _rules_ok(c.get("general_rules"))]
        if bad:
            raise DatasetError(f"cases without a non-empty list of text general_rules: {bad[:5]}")
        if "grading_policies" in data:
            raise DatasetError(f"Group {group.name} uses per-case general_rules, but the file also has "
                               "grading_policies; it is not clear which rules to show")
    return Dataset(path=path, sha256=digest, data=data)


def load_group(name: str, path=None, expected_sha256: str | None = "default") -> Dataset:
    """Load a group's test set: its default file unless given, and the file's pinned hash (or the
    group's) unless given. Checks the group matches."""
    group = GROUPS[name]
    ds = load(path or group.default_path,
              default_sha256(group, path) if expected_sha256 == "default" else expected_sha256)
    if ds.group.name != name:
        raise DatasetError(f"{ds.path} is a Group {ds.group.name} test set, not Group {name}")
    return ds


def _rules_ok(rules) -> bool:
    return isinstance(rules, list) and bool(rules) and all(isinstance(r, str) and r.strip() for r in rules)


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
    test_id_re = ds.group.test_id_re
    groups: dict[str, list[dict]] = {}
    for case in ds.cases:
        tid = case.get("test_id")
        keys = set(case)
        here = []
        if keys != expected_keys:
            here.append(f"fields missing {sorted(expected_keys - keys)}, unexpected {sorted(keys - expected_keys)}")
            problems += [f"{tid}: {p}" for p in here]
            continue
        if not test_id_re.match(tid):
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


def require_selected(ds: Dataset, selection: Selection) -> None:
    """Raise DatasetError if the filters chose no case, naming the test set, its group and the filters.

    Every filter value can exist in the test set while their combination matches nothing (e.g.
    --test-type paraphrase on Group A, which has only originals), and a run with no cases has nothing
    to evaluate.
    """
    if selection.selected_ids:
        return
    try:
        shown = ds.path.resolve().relative_to(REPO)
    except ValueError:
        shown = ds.path
    given = {k: v for k, v in selection.filters.items() if v}
    flags = [f"--{k.replace('_', '-')} {','.join(v)}" for k, v in given.items()]
    alone = [f"{flag}: {sum(c[k] in v for c in ds.cases)}" for flag, (k, v) in zip(flags, given.items())]
    what = (f"the filters {' and '.join(flags)} together match" if len(flags) > 1
            else f"the filter {flags[0]} matches" if flags else "the test set has")
    raise DatasetError(
        f"no test cases selected: {what} none of the {len(ds.cases)} cases in the Group {ds.group.name} test set "
        f"{shown} (SHA-256 {ds.sha256[:12]}…)"
        + (f". Cases each filter matches on its own: {'; '.join(alone)}" if flags else "")
        + ". Change or remove the filters.")
