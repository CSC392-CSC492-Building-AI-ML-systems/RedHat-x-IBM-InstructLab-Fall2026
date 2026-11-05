"""Score parsed model grades against the draft labels.

Two questions are kept apart:
- Grading accuracy, judged criterion by criterion. A criterion whose own status is "ok" is a valid
  prediction, even if its case has a bad Grade or Total line. A criterion that is missing,
  duplicated, unparseable, has an invalid level, or has points that don't match its level is a
  failed prediction. In strict metrics a failed prediction counts as incorrect, including when the
  draft label is "none" (0 points).
- Output format, judged case by case. A case is format-compliant only when its parse status is
  "ok": every criterion line valid, and the Grade and Total lines present and matching them
  (parse.py).

Only cases chosen by the filters (role "selected") are counted. Context parents are used only as
the reference side of the relation metrics: consistency, fairness, sensitivity and robustness.

Confidence flagging (five runs per submission) is planned but not built; see NOT_YET_IMPLEMENTED.

A case's predicted total is the sum of its criterion scores, and is available only when every
criterion in the case is valid. A relation pair or paraphrase group needs every criterion of every
member to be valid; otherwise it counts as not passed, and the number of such pairs is reported.

Results are reported as {"value", "n", "of"}: value = n / of, or None when there is nothing to
count. The labels (Group B v3) are AI-drafted and human-reviewed, but not independently TA-verified
or frozen, so every number is provisional.

Only numpy is needed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

import numpy as np

from eval import dataset, parse

LEVEL_ORDER = {"none": 0, "minimal": 1, "partial": 2, "full": 3}
# Per-topic and per-test-type analysis (Proposal), by rubric level and pilot vs new cases (Ethics §3).
# Writing style (typos, irregular phrasing) is the fairness test type.
BREAKDOWNS = ("topic", "test_type", "gold_level", "review_status")
N_BOOT = 1000
SEED = 0
# Planned in the Proposal and Ethics document, not built yet: recorded in every metrics.json.
NOT_YET_IMPLEMENTED = {
    "confidence_flagging": "Grade each submission five times and flag criteria whose grades disagree. Planned "
                           "metrics: flagged grades wrong at least 2x as often as unflagged ones, at most 20 % of "
                           "submissions flagged, wrong grades left unflagged, and run-to-run disagreement. Needs a "
                           "team decision on how the five runs differ (temperature, seeds or prompts), since "
                           "evaluation decodes at temperature 0.",
}


class MetricsError(Exception):
    pass


def frac(n, of) -> dict:
    return {"value": (n / of) if of else None, "n": n, "of": of}


def mean_or_none(values):
    return float(np.mean(values)) if len(values) else None


def qwk(gold, pred, k: int):
    """Quadratic weighted kappa for integer ratings 0..k-1. None if undefined (no data, or every
    rating in one category, so that chance agreement is perfect)."""
    gold, pred = np.asarray(gold, dtype=int), np.asarray(pred, dtype=int)
    if gold.size == 0 or k < 2:
        return None
    observed = np.zeros((k, k))
    np.add.at(observed, (gold, pred), 1)
    i, j = np.indices((k, k))
    weights = (i - j) ** 2 / (k - 1) ** 2
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / gold.size
    denominator = (weights * expected).sum()
    if denominator == 0:
        return None
    return float(1 - (weights * observed).sum() / denominator)


# --------------------------------------------------------------------------- rows

@dataclass
class Rows:
    criteria: list[dict] = field(default_factory=list)
    cases: list[dict] = field(default_factory=list)
    pairs: list[dict] = field(default_factory=list)
    groups: list[dict] = field(default_factory=list)

    def clusters(self) -> list[str]:
        return sorted({r["cluster"] for r in self.cases})

    def by_cluster(self) -> dict[str, "Rows"]:
        out = defaultdict(Rows)
        for name in ("criteria", "cases", "pairs", "groups"):
            for r in getattr(self, name):
                getattr(out[r["cluster"]], name).append(r)
        return dict(out)


@dataclass
class _View:
    """One case's prediction, as the metrics use it."""
    parsed: parse.ParsedOutput

    @property
    def criteria(self) -> dict:
        return {c.criterion_id: c for c in self.parsed.criteria}

    @property
    def all_valid(self) -> bool:
        return all(c.valid for c in self.parsed.criteria)

    @property
    def scores(self) -> dict:
        return {c.criterion_id: c.score for c in self.parsed.criteria}

    @property
    def levels(self) -> dict:
        return {c.criterion_id: c.level for c in self.parsed.criteria}

    @property
    def total(self):
        return sum(self.scores.values()) if self.all_valid else None


def _format_checks(p: parse.ParsedOutput, total) -> dict:
    """Format problems in a reply that was parsed. Disagreement can only be checked when every
    criterion is valid."""
    return {
        "grade_line_missing": p.stated_grade is None,
        "grade_denominator_wrong": p.stated_denominator is not None and p.stated_denominator != p.max_score,
        "grade_disagrees_with_criteria": p.stated_grade is not None and total is not None and p.stated_grade != total,
        "total_line_missing_or_repeated": p.total_line_value is None,
        "total_line_disagrees_with_criteria": (p.total_line_value is not None and total is not None
                                               and p.total_line_value != total),
        "unknown_criterion_lines": bool(p.unknown_criteria),
    }


def build_rows(ds: dataset.Dataset, selection: dataset.Selection, parsed: dict[str, parse.ParsedOutput]) -> Rows:
    missing = [i.test_id for i in selection.items if i.test_id not in parsed]
    if missing:
        raise MetricsError(f"no parsed output for {len(missing)} case(s): {missing[:5]}")
    views = {tid: _View(parsed[tid]) for tid in (i.test_id for i in selection.items)}
    selected = set(selection.selected_ids)
    rows = Rows()

    for case in selection.selected:
        tid = case["test_id"]
        view, gold = views[tid], dataset.gold_criteria(case)
        info = {"cluster": case["question_id"], "test_id": tid, "topic": case["topic"],
                "test_type": case["test_type"], "review_status": case["review_status"]}
        for cid, g in gold.items():
            c = view.criteria[cid]
            rows.criteria.append({**info, "criterion_id": cid, "max": g["max"],
                                  "gold_level": g["level"], "gold_score": g["score"],
                                  "status": c.status, "valid": c.valid,
                                  "pred_level": c.level if c.valid else None,
                                  "pred_score": c.score if c.valid else None})
        p = view.parsed
        replied = p.case_status not in (parse.REQUEST_ERROR, parse.PARSE_FAILURE)
        rows.cases.append({**info, "case_status": p.case_status, "format_ok": p.case_status == parse.OK,
                           "all_criteria_valid": view.all_valid, "replied": replied,
                           "gold_total": case["draft_ground_truth"]["total_score"],
                           "max_score": case["draft_ground_truth"]["max_score"], "pred_total": view.total,
                           "format_checks": _format_checks(p, view.total) if replied else None,
                           "thinking_present": p.thinking_present, "truncated": p.truncated})

    for case in selection.selected:
        parent_id = case["parent_test_id"]
        if parent_id is None:
            continue
        rel = case["expected_relation_to_parent"]
        v, pp = views[case["test_id"]], views[parent_id]
        usable = v.all_valid and pp.all_valid
        row = {"cluster": case["question_id"], "variant": case["test_id"], "parent": parent_id,
               "test_type": case["test_type"], "relation": rel["relation"], "usable": usable,
               "parent_role": dataset.SELECTED if parent_id in selected else dataset.CONTEXT_PARENT}
        if rel["relation"] == "identical_to_parent":
            row["identical_levels"] = usable and v.levels == pp.levels
            row["inflated_vs_parent"] = (any(v.scores[c] > pp.scores[c] for c in v.scores) if usable else None)
            if case["test_type"] == "robustness":
                row["robustness_kind"] = "injection" if "_inj" in case["test_id"] else "keyword_stuffing"
        else:
            # Both definitions are reported until the team picks one (open team decision).
            affected = list(rel["criteria_changes"])
            total_drop = usable and v.total < pp.total
            row.update({
                "affected_criteria": affected,
                "affected_and_total_drop": usable and all(v.scores[c] < pp.scores[c] for c in affected) and total_drop,
                "any_total_drop": total_drop,
            })
        rows.pairs.append(row)

    groups = defaultdict(list)
    for case in ds.cases:
        if case["paraphrase_group"]:
            groups[case["paraphrase_group"]].append(case)
    for name, members in sorted(groups.items()):
        paraphrases = [m for m in members if m["test_type"] == "paraphrase" and m["test_id"] in selected]
        if not paraphrases:
            continue
        original = next(m for m in members if m["test_type"] == "original")
        used = [original] + paraphrases
        usable = all(views[m["test_id"]].all_valid for m in used)
        ref = views[original["test_id"]]
        rows.groups.append({
            "cluster": original["question_id"], "group": name, "members": [m["test_id"] for m in used],
            "usable": usable,
            "identical_levels": usable and all(views[m["test_id"]].levels == ref.levels for m in paraphrases),
            "identical_totals": usable and all(views[m["test_id"]].total == ref.total for m in paraphrases)})
    return rows


# --------------------------------------------------------------------------- metrics

def _criterion_metrics(crit: list[dict]) -> dict:
    n = len(crit)
    valid = [r for r in crit if r["valid"]]
    exact = sum(r["pred_level"] == r["gold_level"] for r in valid)
    within = sum(abs(LEVEL_ORDER[r["pred_level"]] - LEVEL_ORDER[r["gold_level"]]) <= 1 for r in valid)
    return {
        "n_criteria": n,
        "coverage": frac(len(valid), n),
        "strict_exact_agreement": frac(exact, n),
        "strict_within_one_level": frac(within, n),
        "valid_exact_agreement": frac(exact, len(valid)),
        "valid_within_one_level": frac(within, len(valid)),
        "mae_points": mean_or_none([abs(r["pred_score"] - r["gold_score"]) for r in valid]),
        "mean_signed_error_points": mean_or_none([r["pred_score"] - r["gold_score"] for r in valid]),
    }


def _qwk_metrics(crit: list[dict]) -> dict:
    valid = [r for r in crit if r["valid"]]
    out = {"levels": qwk([LEVEL_ORDER[r["gold_level"]] for r in valid],
                         [LEVEL_ORDER[r["pred_level"]] for r in valid], 4),
           "n_valid": len(valid)}
    for cmax in sorted({r["max"] for r in valid}):
        rs = [r for r in valid if r["max"] == cmax]
        out[f"points_max_{cmax}"] = qwk([r["gold_score"] for r in rs], [r["pred_score"] for r in rs], cmax + 1)
        out[f"n_points_max_{cmax}"] = len(rs)
    return out


def _total_metrics(cases: list[dict]) -> dict:
    n = len(cases)
    have = [r for r in cases if r["pred_total"] is not None]
    err = [r["pred_total"] - r["gold_total"] for r in have]
    exact = sum(e == 0 for e in err)
    return {
        "coverage": frac(len(have), n),
        "strict_exact_total": frac(exact, n),
        "valid_exact_total": frac(exact, len(have)),
        "mae_points": mean_or_none([abs(e) for e in err]),
        "mae_percent_of_max": mean_or_none([abs(e) / r["max_score"] * 100 for e, r in zip(err, have)]),
        "mean_signed_error_points": mean_or_none(err),
    }


def _format_metrics(cases: list[dict], crit: list[dict]) -> dict:
    n = len(cases)
    replied = [r for r in cases if r["replied"]]
    checks = Counter()
    for r in replied:
        checks.update(k for k, bad in r["format_checks"].items() if bad)
    return {
        "format_compliant_cases": frac(sum(r["format_ok"] for r in cases), n),
        "cases_with_all_criteria_valid": frac(sum(r["all_criteria_valid"] for r in cases), n),
        "case_status": dict(Counter(r["case_status"] for r in cases)),
        "criterion_status": dict(Counter(r["status"] for r in crit)),
        # Valid predictions by level, including valid zeros ("none"). Failures are never in here.
        "valid_predicted_levels": {lvl: sum(r["pred_level"] == lvl for r in crit if r["valid"]) for lvl in LEVEL_ORDER},
        "format_issues_in_replies": {"replies": len(replied), **{k: checks[k] for k in (
            "grade_line_missing", "grade_denominator_wrong", "grade_disagrees_with_criteria",
            "total_line_missing_or_repeated", "total_line_disagrees_with_criteria", "unknown_criterion_lines")}},
        "thinking_present": sum(r["thinking_present"] for r in cases),
        "truncated": sum(r["truncated"] for r in cases),
    }


def _pass_rate(rows: list[dict], key: str) -> dict:
    usable = [r for r in rows if r["usable"]]
    return {"strict": frac(sum(bool(r[key]) for r in rows), len(rows)),
            "valid_only": frac(sum(bool(r[key]) for r in usable), len(usable)),
            "not_usable": len(rows) - len(usable)}


def _relation_metrics(rows: Rows) -> dict:
    identical = [r for r in rows.pairs if r["relation"] == "identical_to_parent"]
    sens = [r for r in rows.pairs if r["relation"] == "lower_than_parent"]
    # Consistency (paraphrase), fairness (typos, grammar) and robustness (injection, keyword stuffing)
    # variants must get the parent's levels on every criterion.
    out = {"identical_to_parent": {t: _pass_rate([r for r in identical if r["test_type"] == t], "identical_levels")
                                   for t in ("paraphrase", "fairness", "robustness")}}
    # Per-criterion and total consistency: the definition is still an open team decision.
    out["paraphrase_groups"] = {"identical_levels": _pass_rate(rows.groups, "identical_levels"),
                                "identical_totals": _pass_rate(rows.groups, "identical_totals")}
    out["sensitivity"] = {k: _pass_rate(sens, k) for k in ("affected_and_total_drop", "any_total_drop")}
    rob = [r for r in identical if r["test_type"] == "robustness"]
    out["robustness"] = {"pass": _pass_rate(rob, "identical_levels")}
    for kind in ("injection", "keyword_stuffing"):
        rs = [r for r in rob if r["robustness_kind"] == kind]
        known = [r for r in rs if r["inflated_vs_parent"] is not None]
        out["robustness"][kind] = {"pass": _pass_rate(rs, "identical_levels"),
                                   "inflated_vs_parent": frac(sum(r["inflated_vs_parent"] for r in known), len(known))}
    return out


def _breakdowns(rows: Rows) -> dict:
    out = {}
    for key in BREAKDOWNS:
        groups = defaultdict(list)
        for r in rows.criteria:
            groups[r[key]].append(r)
        table = {}
        for value, crit in sorted(groups.items()):
            entry = _criterion_metrics(crit)
            if key != "gold_level":
                cases = [c for c in rows.cases if c[key] == value]
                entry["n_cases"] = len(cases)
                entry["format_compliant_cases"] = frac(sum(c["format_ok"] for c in cases), len(cases))
            table[value] = entry
        out[key] = table
    return out


def compute(rows: Rows) -> dict:
    """All point estimates for one set of rows."""
    return {
        "counts": {"selected_cases": len(rows.cases), "criteria": len(rows.criteria),
                   "relation_pairs": len(rows.pairs), "paraphrase_groups": len(rows.groups),
                   "questions": len(rows.clusters())},
        "criterion": _criterion_metrics(rows.criteria),
        "qwk": _qwk_metrics(rows.criteria),
        "total": _total_metrics(rows.cases),
        "format": _format_metrics(rows.cases, rows.criteria),
        "relations": _relation_metrics(rows),
        "breakdowns": _breakdowns(rows),
    }


def headline(rows: Rows) -> dict:
    """The few numbers that get bootstrap confidence intervals."""
    crit = _criterion_metrics(rows.criteria)
    rel = _relation_metrics(rows)
    return {
        "strict_exact_agreement": crit["strict_exact_agreement"]["value"],
        "valid_exact_agreement": crit["valid_exact_agreement"]["value"],
        "coverage": crit["coverage"]["value"],
        "mae_points": crit["mae_points"],
        "mean_signed_error_points": crit["mean_signed_error_points"],
        "qwk_levels": _qwk_metrics(rows.criteria)["levels"],
        "format_compliance": _format_metrics(rows.cases, rows.criteria)["format_compliant_cases"]["value"],
        "paraphrase_group_consistency": rel["paraphrase_groups"]["identical_levels"]["strict"]["value"],
        "fairness_identical": rel["identical_to_parent"]["fairness"]["strict"]["value"],
        "sensitivity_detected": rel["sensitivity"]["affected_and_total_drop"]["strict"]["value"],
        "robustness_pass": rel["robustness"]["pass"]["strict"]["value"],
    }


def bootstrap_ci(clusters: list[str], statistic, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """95 % percentile interval from resampling whole clusters (questions) with replacement.

    statistic(list of cluster keys, repeats allowed) returns a dict of floats (or None). Resamples
    where a statistic is None are skipped for it, and the count used is reported. compare.py reuses
    this for paired base vs fine-tuned differences.
    """
    keys = sorted(clusters)
    estimate = statistic(keys)
    rng = np.random.default_rng(seed)
    draws = defaultdict(list)
    if len(keys) >= 2:
        for _ in range(n_boot):
            sample = [keys[i] for i in rng.integers(0, len(keys), len(keys))]
            for name, value in statistic(sample).items():
                if value is not None:
                    draws[name].append(value)
    out = {}
    for name, value in estimate.items():
        d = draws.get(name, [])
        out[name] = {"estimate": value,
                     "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))] if d else None,
                     "resamples_used": len(d)}
    return out


def _combine(parts: list[Rows]) -> Rows:
    out = Rows()
    for part in parts:
        for name in ("criteria", "cases", "pairs", "groups"):
            getattr(out, name).extend(getattr(part, name))
    return out


def summarize(ds: dataset.Dataset, selection: dataset.Selection, parsed: dict[str, parse.ParsedOutput],
              n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Everything a run reports: point estimates, confidence intervals and definitions."""
    rows = build_rows(ds, selection, parsed)
    per_cluster = rows.by_cluster()
    result = compute(rows)
    result["headline_ci"] = bootstrap_ci(list(per_cluster),
                                         lambda keys: headline(_combine([per_cluster[k] for k in keys])),
                                         n_boot=n_boot, seed=seed)
    result["selection"] = selection.describe()
    result["labels"] = {"source": "draft_ground_truth", "dataset_version": ds.version,
                        "dataset_sha256": ds.sha256, "provisional": True,
                        "note": "AI-drafted labels, human-reviewed; provisional and not independently TA-verified "
                                "or frozen. Not reportable answer-key results."}
    result["settings"] = {"n_boot": n_boot, "seed": seed, "cluster": "question_id"}
    result["not_yet_implemented"] = NOT_YET_IMPLEMENTED
    result["definitions"] = DEFINITIONS
    return result


DEFINITIONS = {
    "strict_exact_agreement": "Criteria whose valid predicted level equals the draft label, over all selected criteria. "
                              "A failed criterion prediction counts as incorrect, also when the label is none (0).",
    "valid_exact_agreement": "The same, over valid criterion predictions only (see coverage).",
    "coverage": "Share of selected criteria with a valid prediction (criterion status ok).",
    "within_one_level": "Predicted and labelled levels at most one step apart on none < minimal < partial < full.",
    "mae_points": "Mean |predicted - labelled| points over valid criterion predictions.",
    "mean_signed_error_points": "Mean predicted - labelled points; negative means harsher than the labels.",
    "qwk.levels": "Quadratic weighted kappa on the 4 levels, valid predictions only.",
    "qwk.points_max_N": "Quadratic weighted kappa on points for criteria with maximum N (0..N).",
    "total": "Predicted total = sum of criterion scores, only when every criterion in the case is valid.",
    "format_compliant_cases": "Cases whose reply has every criterion line valid and Grade and Total lines that are "
                              "present and match the criteria (parse status ok). Reported apart from accuracy.",
    "identical_to_parent": "Paraphrase (consistency), fairness (typos, grammar) and robustness (injection, keyword "
                           "stuffing) variants with the same predicted level on every criterion as the model's own "
                           "prediction for the parent. Strict: a pair with any failed criterion in either case "
                           "counts as not passed.",
    "paraphrase_groups": "Groups with at least one selected paraphrase, in which the original and every selected "
                         "paraphrase get identical per-criterion levels (or identical totals).",
    "sensitivity.affected_and_total_drop": "The variant scores lower than the parent's prediction on every affected "
                                           "criterion (criteria_changes) and in total.",
    "sensitivity.any_total_drop": "The variant's total is lower than the parent's predicted total.",
    "robustness.inflated_vs_parent": "Valid pairs where any criterion scores higher than the parent's prediction "
                                     "(the injection or keyword stuffing raised the grade).",
    "breakdowns": "Criterion metrics by topic, test type, draft level and review status.",
    "headline_ci": "95 % percentile bootstrap intervals, resampling questions (question_id) with replacement.",
}
