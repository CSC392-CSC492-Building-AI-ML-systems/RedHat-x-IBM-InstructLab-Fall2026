"""Compare a base-model run with a fine-tuned run of the same evaluation.

    python eval/compare.py --base runs/<base run> --fine-tuned runs/<fine-tuned run> --out runs/compare

Both runs must be complete and must have used the same dataset, prompt template, selected cases
(and context parents), filters and decoding settings, with the base model under the fine-tuned
adapter. Both must have sent byte-identical prompts, system messages included, and every saved
reply must have been made from its saved prompt. Otherwise the comparison is refused and every
mismatch is listed.

Both runs are re-scored from their saved raw outputs with the current parser and metrics, so the
two models are always scored by identical code. If a run's saved metrics.json differs from the
re-scored one (the code changed since the run), a warning says so.

The headline metrics get the difference fine-tuned − base with a paired 95 % bootstrap interval
(the same resampled questions for both models) and a verdict that accounts for direction: lower
is better for MAE, and mean signed error is judged by its distance from zero. The report also shows
coverage and parsing failures for both models, criterion-level changes, and per-topic and
per-test-type agreement. Every metric of both models is in compare.json under "metrics".

Writes <out>/<timestamp>_compare/compare.json and compare.md. Every result is provisional: the
Group B labels are AI-drafted and human-reviewed, but not independently TA-verified or frozen.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as `python eval/compare.py`
    sys.path[0] = str(Path(__file__).resolve().parent.parent)

from eval import dataset, metrics, parse, prompt, report, run_eval  # noqa: E402

COMPUTED_KEYS = ("counts", "criterion", "qwk", "total", "format", "relations", "breakdowns")
HIGHER = "higher_is_better"
LOWER = "lower_is_better"
NEUTRAL = "no_direction"
IMPROVED, REGRESSED, UNCHANGED, NA, NOT_JUDGED = "improved", "regressed", "unchanged", "n/a", "-"
# Which way is better for each headline metric. The signed error itself has no direction; its
# distance from zero (abs_mean_signed_error_points) does.
HEADLINE_DIRECTION = {"mae_points": LOWER, "abs_mean_signed_error_points": LOWER,
                      "mean_signed_error_points": NEUTRAL}


class CompareError(Exception):
    pass


# --------------------------------------------------------------------------- loading and checks

def load_run(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    if not (run_dir / run_eval.CONFIG).exists():
        raise CompareError(f"{run_dir} is not a run folder (no config.json)")
    config = json.loads((run_dir / run_eval.CONFIG).read_text(encoding="utf-8"))
    if "rescore" in config:
        raise CompareError(f"{run_dir} is a rescore folder; pass the run folder itself")
    raw_path = run_dir / run_eval.RAW
    raw = run_eval.read_replies(raw_path) if raw_path.exists() else []
    metrics_path = run_dir / run_eval.METRICS
    return {"dir": run_dir, "config": config, "raw": raw,
            "saved_metrics": json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else None,
            "prompts_sha256": dataset.sha256_file(run_dir / run_eval.PROMPTS)
            if (run_dir / run_eval.PROMPTS).exists() else None}


def check_compatible(base: dict, ft: dict) -> list[str]:
    """Every reason the two runs can't be compared (empty if they can)."""
    a, b = base["config"], ft["config"]
    problems = []
    for name, run in (("base", base), ("fine-tuned", ft)):
        if run["config"].get("status") != "complete":
            problems.append(f"the {name} run is not complete (status {run['config'].get('status')})")
    if a["model"]["role"] != "base":
        problems.append(f"the --base run is a {a['model']['role']} run")
    if b["model"]["role"] != "fine_tuned":
        problems.append(f"the --fine-tuned run is a {b['model']['role']} run")
    if a["model"]["served_model"] == b["model"]["served_model"]:
        problems.append(f"both runs used the served model {a['model']['served_model']!r}")
    base_model = a["model"].get("base_model")
    under = (b["model"].get("adapter") or {}).get("settings") or {}
    if base_model and under.get("base_model") and base_model != under["base_model"]:
        problems.append(f"the base run used {base_model!r}, but the adapter was trained on {under['base_model']!r}")
    checks = [
        ("dataset SHA-256", a["dataset"]["sha256"], b["dataset"]["sha256"]),
        ("prompt template", a["prompt"]["template_sha256"], b["prompt"]["template_sha256"]),
        ("prompts file (recorded)", a["prompts_file"]["sha256"], b["prompts_file"]["sha256"]),
        ("prompts file (on disk)", base["prompts_sha256"], ft["prompts_sha256"]),
        ("filters", a["selection"]["filters"], b["selection"]["filters"]),
        ("selected cases", a["selection"]["selected_case_ids"], b["selection"]["selected_case_ids"]),
        ("context parents", a["selection"]["context_parent_ids"], b["selection"]["context_parent_ids"]),
        ("decoding settings", a["decoding"], b["decoding"]),
    ]
    problems += [f"the runs differ in {what}: {x!r} vs {y!r}" for what, x, y in checks if x != y]
    for name, run in (("base", base), ("fine-tuned", ft)):
        if run["prompts_sha256"] != run["config"]["prompts_file"]["sha256"]:
            problems.append(f"the {name} run's prompts.jsonl no longer matches its config")
    return problems


def warnings_for(base: dict, ft: dict) -> list[str]:
    a, b = base["config"], ft["config"]
    out = []
    if not a["prompt"]["layout_verified"]:
        out.append("the prompt's student-answer layout has not been verified against Fir training data")
    if not a["model"].get("base_model"):
        out.append("the base run does not record its base model, so it can't be checked against the adapter's")
    if a["code"].get("git_commit") != b["code"].get("git_commit"):
        out.append(f"the runs were made from different code: {a['code'].get('git_commit')} vs "
                   f"{b['code'].get('git_commit')}")
    if (a.get("server") or {}).get("vllm_version") != (b.get("server") or {}).get("vllm_version"):
        out.append("the runs report different vLLM versions")
    return out


def check_same_prompts(a: dict, b: dict) -> None:
    """Both runs must have sent exactly the same messages (system and user) for every case."""
    differ = sorted(t for t in set(a) | set(b) if a.get(t) != b.get(t))
    if differ:
        raise CompareError(f"the two runs sent different prompts for {len(differ)} case(s), e.g. {differ[:3]}")


def rescore_run(ds: dataset.Dataset, selection: dataset.Selection, run: dict, messages: dict) -> tuple[dict, metrics.Rows]:
    raw = {}
    for g in run["raw"]:
        if g.test_id in raw:
            raise CompareError(f"{run['dir']}: {g.test_id} has more than one saved reply")
        raw[g.test_id] = g
    by_id = ds.by_id()
    parsed = {}
    for item in selection.items:
        g = raw.get(item.test_id)
        if g is None:
            raise CompareError(f"{run['dir']}: no saved reply for {item.test_id}")
        if g.prompt_sha256 != prompt.messages_sha256(messages[item.test_id]):
            raise CompareError(f"{run['dir']}: the reply for {item.test_id} was made from a different prompt")
        parsed[item.test_id] = parse.parse_generation(g, by_id[item.test_id])
    return parsed, metrics.build_rows(ds, selection, parsed)


# --------------------------------------------------------------------------- differences

def judge(d: str, a, b) -> str:
    """improved / regressed / unchanged for a change from base (a) to fine-tuned (b)."""
    if d == NEUTRAL:
        return NOT_JUDGED
    if a is None or b is None:
        return NA
    if abs(b - a) < 1e-12:
        return UNCHANGED
    better = b > a if d == HIGHER else b < a
    return IMPROVED if better else REGRESSED


def paired_bootstrap(rows_a: metrics.Rows, rows_b: metrics.Rows, n_boot: int, seed: int) -> dict:
    """Intervals for fine-tuned − base on the headline metrics, resampling the same questions for both."""
    ca, cb = rows_a.by_cluster(), rows_b.by_cluster()
    if set(ca) != set(cb):
        raise CompareError("the two runs cover different questions")

    def statistic(keys):
        ha = metrics.headline(metrics._combine([ca[k] for k in keys]))
        hb = metrics.headline(metrics._combine([cb[k] for k in keys]))
        out = {name: (hb[name] - ha[name]) if ha[name] is not None and hb[name] is not None else None for name in ha}
        if ha["mean_signed_error_points"] is not None and hb["mean_signed_error_points"] is not None:
            out["abs_mean_signed_error_points"] = abs(hb["mean_signed_error_points"]) - abs(ha["mean_signed_error_points"])
        return out

    result = metrics.bootstrap_ci(list(ca), statistic, n_boot=n_boot, seed=seed)
    whole_a, whole_b = metrics.headline(rows_a), metrics.headline(rows_b)
    whole_a["abs_mean_signed_error_points"] = (abs(whole_a["mean_signed_error_points"])
                                               if whole_a["mean_signed_error_points"] is not None else None)
    whole_b["abs_mean_signed_error_points"] = (abs(whole_b["mean_signed_error_points"])
                                               if whole_b["mean_signed_error_points"] is not None else None)
    for name, entry in result.items():
        d = HEADLINE_DIRECTION.get(name, HIGHER)
        entry.update({"base": whole_a[name], "fine_tuned": whole_b[name], "direction": d,
                      "verdict": judge(d, whole_a[name], whole_b[name]),
                      "ci_excludes_zero": (entry["ci95"] is not None
                                           and (entry["ci95"][0] > 0 or entry["ci95"][1] < 0))})
    return result


def paired_outcomes(rows_a: metrics.Rows, rows_b: metrics.Rows) -> dict:
    """Per criterion: correct (valid and matching the label) in both runs, only one, or neither."""
    key = lambda r: (r["test_id"], r["criterion_id"])
    a = {key(r): r["valid"] and r["pred_level"] == r["gold_level"] for r in rows_a.criteria}
    b = {key(r): r["valid"] and r["pred_level"] == r["gold_level"] for r in rows_b.criteria}
    if set(a) != set(b):
        raise CompareError("the two runs grade different criteria")
    out = {"both_correct": 0, "base_only_correct": 0, "fine_tuned_only_correct": 0, "neither_correct": 0}
    for k in a:
        out[{(True, True): "both_correct", (True, False): "base_only_correct",
             (False, True): "fine_tuned_only_correct", (False, False): "neither_correct"}[(a[k], b[k])]] += 1
    changed = sorted({k[0] for k in a if a[k] != b[k]})
    return {**out, "criteria": len(a), "cases_with_changes": changed}


# --------------------------------------------------------------------------- compare

def compare(base_dir: Path, ft_dir: Path, n_boot: int = metrics.N_BOOT, seed: int = metrics.SEED) -> dict:
    base, ft = load_run(base_dir), load_run(ft_dir)
    problems = check_compatible(base, ft)
    if problems:
        raise CompareError("the runs can't be compared:\n  - " + "\n  - ".join(problems))
    cfg = base["config"]
    ds = dataset.load(cfg["dataset"]["path"], expected_sha256=cfg["dataset"]["sha256"])
    f = cfg["selection"]["filters"]
    selection = dataset.select(ds, test_types=f["test_type"], topics=f["topic"], question_ids=f["question_id"])
    if selection.describe() != cfg["selection"]:
        raise CompareError("the selection rebuilt from the configs does not match the runs")
    messages = run_eval.read_prompts(base["dir"], cfg)
    check_same_prompts(messages, run_eval.read_prompts(ft["dir"], ft["config"]))

    _, rows_a = rescore_run(ds, selection, base, messages)
    _, rows_b = rescore_run(ds, selection, ft, messages)
    ma, mb = metrics.compute(rows_a), metrics.compute(rows_b)
    warnings = warnings_for(base, ft)
    for name, run, m in (("base", base, ma), ("fine-tuned", ft, mb)):
        saved = run["saved_metrics"]
        if saved is None or {k: saved.get(k) for k in COMPUTED_KEYS} != json.loads(json.dumps({k: m[k] for k in COMPUTED_KEYS})):
            warnings.append(f"the {name} run's saved metrics.json differs from re-scoring it with the current code; "
                            "this comparison uses the re-scored values")
    dataset.verify_unchanged(ds)
    return {
        "provisional": True,
        "note": run_eval.PROVISIONAL_NOTE,
        "created_at": run_eval.now(),
        "runs": {"base": str(base["dir"]), "fine_tuned": str(ft["dir"])},
        "models": {"base": cfg["model"], "fine_tuned": ft["config"]["model"]},
        "shared": {"dataset": cfg["dataset"], "prompt": cfg["prompt"], "prompts_file_sha256": base["prompts_sha256"],
                   "decoding": cfg["decoding"], "selection": cfg["selection"],
                   "selection_headline": cfg["selection_headline"]},
        "warnings": warnings,
        "settings": {"n_boot": n_boot, "seed": seed, "cluster": "question_id", "code": run_eval.git_info()},
        "headline": paired_bootstrap(rows_a, rows_b, n_boot, seed),
        "paired_criterion_outcomes": paired_outcomes(rows_a, rows_b),
        "metrics": {"base": ma, "fine_tuned": mb},
        "not_yet_implemented": metrics.NOT_YET_IMPLEMENTED,
        "definitions": metrics.DEFINITIONS,
    }


# --------------------------------------------------------------------------- report

def signed(x) -> str:
    return "n/a" if x is None else f"{x:+.3f}"


def render(result: dict) -> str:
    sh, mb, mf = result["shared"], result["metrics"]["base"], result["metrics"]["fine_tuned"]
    lines = ["# Base vs fine-tuned comparison", "", report.PROVISIONAL, ""]
    if not sh["prompt"]["layout_verified"]:
        lines += [report.LAYOUT_UNVERIFIED, ""]
    lines += [f"> **Warning.** {w}" for w in result["warnings"]] + ([""] if result["warnings"] else [])
    lines += ["Difference = fine-tuned − base. The verdict accounts for direction: for MAE lower is better, "
              "and the signed error is judged by its distance from zero.", ""]
    lines += ["## Runs", ""]
    lines += report.table(["", "Base", "Fine-tuned"], [
        ["Run folder", result["runs"]["base"], result["runs"]["fine_tuned"]],
        ["Served model", result["models"]["base"]["served_model"], result["models"]["fine_tuned"]["served_model"]],
        ["Adapter", (result["models"]["base"].get("adapter") or {}).get("path"),
         (result["models"]["fine_tuned"].get("adapter") or {}).get("path")],
    ])
    lines += report.table(["Shared", ""], [
        ["Dataset", f"{sh['dataset']['version']}, sha256 `{sh['dataset']['sha256'][:12]}…`"],
        ["Prompt template", f"{sh['prompt']['template_version']}, sha256 `{sh['prompt']['template_sha256'][:12]}…`"],
        ["Prompts file", f"sha256 `{sh['prompts_file_sha256'][:12]}…`"],
        ["Decoding", ", ".join(f"{k}={v}" for k, v in sh["decoding"].items())],
        ["Cases", sh["selection_headline"]],
    ])

    lines += ["## Headline (paired 95 % bootstrap over questions)", ""]
    lines += report.table(["Metric", "Base", "Fine-tuned", "Difference [95 % CI]", "Verdict", "CI excludes 0"], [
        [name, e["base"], e["fine_tuned"],
         f"{signed(e['estimate'])} " + (f"[{e['ci95'][0]:+.3f}, {e['ci95'][1]:+.3f}]" if e["ci95"] else "(no interval)"),
         e["verdict"], "yes" if e["ci_excludes_zero"] else "no"]
        for name, e in result["headline"].items()])

    lines += ["## Coverage and parsing failures", ""]
    fb, ff = mb["format"], mf["format"]
    status = sorted(set(fb["case_status"]) | set(ff["case_status"]))
    crit_status = sorted(set(fb["criterion_status"]) | set(ff["criterion_status"]))
    lines += report.table(["", "Base", "Fine-tuned"], [
        ["Criterion coverage (valid predictions)", mb["criterion"]["coverage"], mf["criterion"]["coverage"]],
        ["Cases with every criterion valid", fb["cases_with_all_criteria_valid"], ff["cases_with_all_criteria_valid"]],
        ["Format-compliant cases", fb["format_compliant_cases"], ff["format_compliant_cases"]],
        *[[f"Cases: {s}", fb["case_status"].get(s, 0), ff["case_status"].get(s, 0)] for s in status],
        *[[f"Criteria: {s}", fb["criterion_status"].get(s, 0), ff["criterion_status"].get(s, 0)] for s in crit_status],
        *[[f"Format issue: {k}", fb["format_issues_in_replies"][k], ff["format_issues_in_replies"][k]]
          for k in fb["format_issues_in_replies"] if k != "replies"],
        ["Thinking present / truncated", f"{fb['thinking_present']} / {fb['truncated']}",
         f"{ff['thinking_present']} / {ff['truncated']}"],
    ])

    po = result["paired_criterion_outcomes"]
    lines += ["## Criterion-level changes", ""]
    lines += report.table(["", "Criteria"], [["Correct in both", po["both_correct"]],
                                             ["Correct only for base (regressions)", po["base_only_correct"]],
                                             ["Correct only for fine-tuned (improvements)", po["fine_tuned_only_correct"]],
                                             ["Correct in neither", po["neither_correct"]]])
    if po["cases_with_changes"]:
        lines += ["Cases with a changed criterion: " + ", ".join(f"`{t}`" for t in po["cases_with_changes"]), ""]

    lines += ["## Strict exact agreement by topic, test type and draft level", ""]
    for key in ("topic", "test_type", "gold_level"):
        gb, gf = mb["breakdowns"][key], mf["breakdowns"][key]
        rows = []
        for value in gb:
            a, b = gb[value]["strict_exact_agreement"], gf[value]["strict_exact_agreement"]
            diff = b["value"] - a["value"] if a["value"] is not None and b["value"] is not None else None
            rows.append([value, a, b, signed(diff)])
        lines += [f"### By {key.replace('_', ' ')}", ""]
        lines += report.table([key, "Base", "Fine-tuned", "Difference"], rows)
    lines += ["## Not yet implemented", ""]
    lines += [f"- **{name.replace('_', ' ').capitalize()}:** {text}" for name, text in result["not_yet_implemented"].items()]
    lines += ["", "Every metric of both models is in compare.json under `metrics`.", ""]
    return "\n".join(lines)


def write(result: dict, out: Path) -> Path:
    run_eval.check_out_dir(out)
    out.mkdir(parents=True, exist_ok=True)
    folder = out / f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}_compare"
    n = 1
    while folder.exists():
        n += 1
        folder = out / f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}_compare_{n}"
    folder.mkdir()
    run_eval.write_json(folder / "compare.json", result)
    (folder / "compare.md").write_text(render(result), encoding="utf-8")
    return folder


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", required=True, help="the base model's run folder")
    p.add_argument("--fine-tuned", required=True, help="the fine-tuned model's run folder")
    p.add_argument("--out", required=True, help="folder for the comparison")
    p.add_argument("--n-boot", type=int, default=metrics.N_BOOT)
    p.add_argument("--boot-seed", type=int, default=metrics.SEED)
    args = p.parse_args(argv)
    try:
        run_eval.check_out_dir(Path(args.out))
        result = compare(Path(args.base), Path(args.fine_tuned), n_boot=args.n_boot, seed=args.boot_seed)
        folder = write(result, Path(args.out))
    except (CompareError, run_eval.RunError, dataset.DatasetError, metrics.MetricsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
