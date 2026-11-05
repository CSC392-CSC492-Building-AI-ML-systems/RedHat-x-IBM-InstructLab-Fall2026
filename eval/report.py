"""Write a run's summary.md from its config and metrics."""

from __future__ import annotations

PROVISIONAL = ("> **PROVISIONAL LABELS.** Scored against the Group B AI-drafted labels (draft v3), human-reviewed; "
               "provisional and not independently TA-verified or frozen. These are not answer-key results and must "
               "not be reported as such.")
LAYOUT_UNVERIFIED = ("> **Prompt layout unverified.** The student-answer layout of the evaluation prompt has not "
                     "yet been checked against real training data on Fir (eval/PROMPT.md).")


def fmt(x, digits: int = 3) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, dict) and "value" in x:
        return f"{fmt(x['value'], digits)} ({x['n']}/{x['of']})"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def ci(entry: dict) -> str:
    if entry["ci95"] is None:
        return f"{fmt(entry['estimate'])} (no interval)"
    lo, hi = entry["ci95"]
    return f"{fmt(entry['estimate'])} [{lo:.3f}, {hi:.3f}]"


def table(header: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(fmt(c) for c in row) + " |" for row in rows]
    return lines + [""]


def banners(config: dict) -> list[str]:
    out = [PROVISIONAL, ""]
    if not config["prompt"]["layout_verified"]:
        out += [LAYOUT_UNVERIFIED, ""]
    if config.get("status") != "complete":
        out += [f"> **Run {config.get('status', 'unknown').upper()}.** {config.get('status_detail', '')}", ""]
    for warning in config.get("warnings", []):
        out += [f"> **Warning.** {warning}", ""]
    return out


def run_info(config: dict) -> list[str]:
    model, ds, pr = config["model"], config["dataset"], config["prompt"]
    adapter = model.get("adapter") or {}
    rows = [
        ["Model", f"{model['role']} (served as `{model['served_model']}`)"],
        ["Base model", model.get("base_model")],
        ["Adapter", adapter.get("path")],
        ["Backend", config["backend"]["backend"]],
        ["Decoding", ", ".join(f"{k}={v}" for k, v in config["decoding"].items())],
        ["Dataset", f"{ds['version']}, sha256 `{ds['sha256'][:12]}…`"],
        ["Prompt template", f"{pr['template_version']}, sha256 `{pr['template_sha256'][:12]}…`"],
        ["Prompts file", f"sha256 `{config['prompts_file']['sha256'][:12]}…`"],
        ["Cases", config["selection_headline"]],
        ["Code", f"{config['code']['git_commit'] or 'unknown'}{' (uncommitted changes)' if config['code']['git_dirty'] else ''}"],
        ["Created", config["created_at"]],
    ]
    return table(["", ""], rows)


def failed_cases(parsed_records: list[dict], selected_ids: set) -> list[str]:
    bad = [r for r in parsed_records if r["case_status"] != "ok"]
    if not bad:
        return ["All replies were format-compliant.", ""]
    rows = [[r["test_id"], "selected" if r["test_id"] in selected_ids else "context parent", r["case_status"],
             "; ".join(r["issues"])[:160]] for r in bad]
    return table(["Case", "Role", "Status", "Issues"], rows)


def render_summary(config: dict, metrics: dict | None, parsed_records: list[dict] | None) -> str:
    lines = [f"# Evaluation run: {config['model']['role']}", ""] + banners(config) + ["## Run", ""] + run_info(config)
    if metrics is None:
        lines += ["No metrics: the run did not finish. Start a new run.", ""]
        return "\n".join(lines)

    c, f, rel, q = metrics["criterion"], metrics["format"], metrics["relations"], metrics["qwk"]
    lines += ["## Headline (95 % bootstrap intervals over questions)", ""]
    lines += table(["Metric", "Estimate [95 % CI]"], [[k, ci(v)] for k, v in metrics["headline_ci"].items()])

    lines += ["## Coverage and output format", ""]
    lines += table(["", ""], [
        ["Criterion coverage (valid predictions)", c["coverage"]],
        ["Cases with every criterion valid", f["cases_with_all_criteria_valid"]],
        ["Format-compliant cases", f["format_compliant_cases"]],
        ["Case status", ", ".join(f"{k} {v}" for k, v in sorted(f["case_status"].items()))],
        ["Criterion status", ", ".join(f"{k} {v}" for k, v in sorted(f["criterion_status"].items()))],
        ["Valid predictions by level", ", ".join(f"{k} {v}" for k, v in f["valid_predicted_levels"].items())],
        ["Format issues in replies", ", ".join(f"{k} {v}" for k, v in f["format_issues_in_replies"].items())],
        ["Thinking present / truncated", f"{f['thinking_present']} / {f['truncated']}"],
    ])

    lines += ["## Criterion accuracy", ""]
    lines += table(["", "Strict (failures count as wrong)", "Valid predictions only"], [
        ["Exact level", c["strict_exact_agreement"], c["valid_exact_agreement"]],
        ["Within one level", c["strict_within_one_level"], c["valid_within_one_level"]],
        ["MAE (points)", None, c["mae_points"]],
        ["Mean signed error (points)", None, c["mean_signed_error_points"]],
    ])
    lines += table(["QWK", "Value", "n"], [[k, v, q.get("n_" + k, q["n_valid"])]
                                          for k, v in q.items() if not k.startswith("n_")])
    t = metrics["total"]
    lines += ["## Totals (sum of valid criterion scores)", ""]
    lines += table(["", ""], [["Coverage", t["coverage"]], ["Exact total (strict)", t["strict_exact_total"]],
                              ["Exact total (valid only)", t["valid_exact_total"]], ["MAE (points)", t["mae_points"]],
                              ["MAE (% of max)", t["mae_percent_of_max"]],
                              ["Mean signed error (points)", t["mean_signed_error_points"]]])

    lines += ["## Consistency, fairness, sensitivity and robustness", "",
              "Strict: a pair with a failed criterion in either case counts as not passed.", ""]
    rows = []
    for name, entry in [("Consistency: paraphrase identical to original", rel["identical_to_parent"]["paraphrase"]),
                        ("Consistency: paraphrase groups, identical levels", rel["paraphrase_groups"]["identical_levels"]),
                        ("Consistency: paraphrase groups, identical totals", rel["paraphrase_groups"]["identical_totals"]),
                        ("Fairness: typo/grammar variant identical", rel["identical_to_parent"]["fairness"]),
                        ("Sensitivity: affected criterion and total drop", rel["sensitivity"]["affected_and_total_drop"]),
                        ("Sensitivity: any total drop", rel["sensitivity"]["any_total_drop"]),
                        ("Robustness: injection", rel["robustness"]["injection"]["pass"]),
                        ("Robustness: keyword stuffing", rel["robustness"]["keyword_stuffing"]["pass"])]:
        rows.append([name, entry["strict"], entry["valid_only"], entry["not_usable"]])
    lines += table(["", "Strict", "Valid pairs only", "Pairs not usable"], rows)
    lines += table(["Grade raised above the parent's", "Valid pairs"],
                   [[k, rel["robustness"][k]["inflated_vs_parent"]] for k in ("injection", "keyword_stuffing")])

    lines += ["## Breakdowns", ""]
    for key, groups in metrics["breakdowns"].items():
        lines += [f"### By {key.replace('_', ' ')}", ""]
        lines += table([key, "Criteria", "Coverage", "Strict exact", "Valid exact", "MAE", "Signed error"],
                       [[value, e["n_criteria"], e["coverage"], e["strict_exact_agreement"],
                         e["valid_exact_agreement"], e["mae_points"], e["mean_signed_error_points"]]
                        for value, e in groups.items()])

    lines += ["## Replies that were not format-compliant", ""]
    lines += failed_cases(parsed_records or [], set(config["selection"]["selected_case_ids"]))
    lines += ["## Not yet implemented", ""]
    lines += [f"- **{name.replace('_', ' ').capitalize()}:** {text}" for name, text in metrics["not_yet_implemented"].items()]
    lines += ["", "Definitions of every metric are in metrics.json under `definitions`.", ""]
    return "\n".join(lines)
