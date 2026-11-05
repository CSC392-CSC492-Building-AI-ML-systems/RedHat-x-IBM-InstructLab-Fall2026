"""Metric tests on the synthetic dataset: 18 cases, 46 criteria, 4 questions (see fixtures.py). The
expected numbers are worked out by hand from that dataset."""

import json
import unittest

from eval import dataset, metrics, parse
from eval.tests import test_set_guard
from eval.tests.fixtures import MINI_SIZE, MiniDatasetTest, drop_line, mid, render_grade, with_levels

setUpModule, tearDownModule = test_set_guard()

N_CASES, N_CRITERIA = MINI_SIZE["cases"], MINI_SIZE["criteria"]
ZERO_CASE = mid("beta_02_ans01")    # draft label 0/7, every criterion "none", with an injection variant
ALL_FULL = mid("alpha_01_ans02")    # draft label 10/10, no variants


class Base(MiniDatasetTest):
    def run_metrics(self, replies=None, selection=None):
        selection = selection or dataset.select(self.ds)
        parsed = {}
        for item in selection.items:
            text = (replies or {}).get(item.test_id, render_grade(item.case))
            parsed[item.test_id] = parse.parse_text(text, item.case["rubric"], test_id=item.test_id)
        rows = metrics.build_rows(self.ds, selection, parsed)
        return metrics.compute(rows), rows, parsed

    def reply(self, tid, changes=None):
        case = self.cases[tid]
        return render_grade(case, with_levels(case, changes or {}))

    def gold_none(self):
        return sum(g["level"] == "none" for c in self.ds.cases for g in c["draft_ground_truth"]["criteria"])


class QWKTest(unittest.TestCase):
    def test_qwk(self):
        self.assertEqual(metrics.qwk([0, 1, 2, 3], [0, 1, 2, 3], 4), 1.0)
        # observed disagreement 1, expected 2 (worked out by hand)
        self.assertAlmostEqual(metrics.qwk([0, 0, 1, 1], [0, 1, 1, 1], 2), 0.5)
        self.assertAlmostEqual(metrics.qwk([0, 1, 2], [2, 1, 0], 3), -1.0)
        # undefined
        self.assertIsNone(metrics.qwk([], [], 4))
        self.assertIsNone(metrics.qwk([2, 2, 2], [2, 2, 2], 4))


class PerfectRunTest(Base):
    def test_perfect_run_scores_perfectly(self):
        m, rows, _ = self.run_metrics()
        crit = m["criterion"]
        self.assertEqual(m["counts"], {"selected_cases": N_CASES, "criteria": N_CRITERIA,
                                       "relation_pairs": MINI_SIZE["pairs"], "paraphrase_groups": MINI_SIZE["groups"],
                                       "questions": MINI_SIZE["questions"]})
        for key in ("coverage", "strict_exact_agreement", "valid_exact_agreement", "strict_within_one_level"):
            self.assertEqual(crit[key]["value"], 1.0, key)
        self.assertEqual((crit["mae_points"], crit["mean_signed_error_points"]), (0.0, 0.0))
        self.assertEqual(m["qwk"]["levels"], 1.0)
        self.assertEqual(m["qwk"]["points_max_3"], 1.0)
        self.assertEqual(m["qwk"]["points_max_4"], 1.0)
        self.assertEqual(m["total"]["strict_exact_total"]["value"], 1.0)
        self.assertEqual(m["format"]["format_compliant_cases"]["value"], 1.0)
        self.assertEqual(m["format"]["criterion_status"], {"ok": N_CRITERIA})
        self.assertEqual(sum(m["format"]["valid_predicted_levels"].values()), N_CRITERIA)
        rel = m["relations"]
        pairs = {t: rel["identical_to_parent"][t]["strict"] for t in ("paraphrase", "fairness", "robustness")}
        self.assertEqual(pairs, {"paraphrase": {"value": 1.0, "n": 3, "of": 3},
                                 "fairness": {"value": 1.0, "n": 2, "of": 2},
                                 "robustness": {"value": 1.0, "n": 3, "of": 3}})
        self.assertEqual(rel["paraphrase_groups"]["identical_levels"]["strict"]["value"], 1.0)
        self.assertEqual(rel["paraphrase_groups"]["identical_totals"]["strict"]["value"], 1.0)
        for key in ("affected_and_total_drop", "any_total_drop"):
            self.assertEqual(rel["sensitivity"][key]["strict"], {"value": 1.0, "n": 2, "of": 2}, key)
        self.assertEqual(rel["robustness"]["pass"]["strict"]["of"], 3)
        self.assertEqual(rel["robustness"]["injection"]["inflated_vs_parent"], {"value": 0.0, "n": 0, "of": 2})
        self.assertEqual(rel["robustness"]["keyword_stuffing"]["pass"]["strict"]["of"], 1)

    def test_valid_zeros_counted_as_valid_and_correct(self):
        m, rows, _ = self.run_metrics()
        self.assertGreater(self.gold_none(), 0)
        self.assertEqual(m["format"]["valid_predicted_levels"]["none"], self.gold_none())
        zero_rows = [r for r in rows.criteria if r["test_id"] == ZERO_CASE]
        self.assertTrue(all(r["valid"] and r["pred_score"] == 0 and r["gold_score"] == 0 for r in zero_rows))


class FailureAccountingTest(Base):
    def test_failures_count_as_incorrect(self):
        m, rows, _ = self.run_metrics({ZERO_CASE: "I would give this 0."})
        n, k = N_CRITERIA, len(self.cases[ZERO_CASE]["rubric"])
        crit = m["criterion"]
        self.assertEqual(crit["strict_exact_agreement"], {"value": (n - k) / n, "n": n - k, "of": n})
        self.assertEqual(crit["valid_exact_agreement"]["value"], 1.0)
        self.assertEqual(crit["coverage"], {"value": (n - k) / n, "n": n - k, "of": n})
        self.assertEqual(m["format"]["case_status"]["parse_failure"], 1)
        self.assertEqual(m["format"]["criterion_status"]["missing"], k)
        # the failures are not counted as valid "none" predictions
        self.assertEqual(m["format"]["valid_predicted_levels"]["none"], self.gold_none() - k)
        self.assertEqual(crit["mae_points"], 0.0)  # MAE is over valid predictions; coverage shows the rest
        # its robustness pair (the injection variant) can't pass
        rob = m["relations"]["robustness"]["pass"]
        self.assertEqual((rob["strict"]["n"], rob["strict"]["of"], rob["not_usable"]), (2, 3, 1))
        self.assertEqual(rob["valid_only"]["value"], 1.0)
        self.assertEqual(m["total"]["coverage"]["n"], N_CASES - 1)

        selection = dataset.select(self.ds)
        parsed = {i.test_id: parse.parse_text(render_grade(i.case), i.case["rubric"]) for i in selection.items}
        parsed[ZERO_CASE] = parse.parse_text(None, self.cases[ZERO_CASE]["rubric"], error="Timeout")
        m = metrics.compute(metrics.build_rows(self.ds, selection, parsed))
        self.assertEqual(m["format"]["case_status"]["request_error"], 1)
        self.assertLess(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        self.assertEqual(m["format"]["format_issues_in_replies"]["replies"], N_CASES - 1)

    def test_format_failure_is_not_accuracy_failure(self):
        text = render_grade(self.cases[ALL_FULL]).replace("**Grade:** 10 / 10", "**Grade:** 9 / 10")
        m, rows, parsed = self.run_metrics({ALL_FULL: text})
        self.assertEqual(parsed[ALL_FULL].case_status, "inconsistent_total")
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        self.assertEqual(m["format"]["format_compliant_cases"], {"value": (N_CASES - 1) / N_CASES, "n": N_CASES - 1, "of": N_CASES})
        self.assertEqual(m["format"]["format_issues_in_replies"]["grade_disagrees_with_criteria"], 1)
        self.assertEqual(m["total"]["strict_exact_total"]["value"], 1.0)  # total comes from the criteria
        self.assertEqual(m["relations"]["identical_to_parent"]["paraphrase"]["strict"]["value"], 1.0)

        m, _, parsed = self.run_metrics({ALL_FULL: drop_line(render_grade(self.cases[ALL_FULL]), "Total:")})
        self.assertEqual(parsed[ALL_FULL].case_status, "inconsistent_total")
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        self.assertEqual(m["format"]["format_compliant_cases"]["n"], N_CASES - 1)
        self.assertEqual(m["format"]["format_issues_in_replies"]["total_line_missing_or_repeated"], 1)

    def test_one_missing_criterion_only_costs_that_criterion(self):
        tid = mid("alpha_01_ans01_para2")
        m, rows, _ = self.run_metrics({tid: drop_line(render_grade(self.cases[tid]), "- C2 ")})
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["n"], N_CRITERIA - 1)
        self.assertEqual(m["criterion"]["valid_exact_agreement"]["value"], 1.0)
        same_case = [r for r in rows.criteria if r["test_id"] == tid]
        self.assertEqual([(r["criterion_id"], r["valid"]) for r in same_case],
                         [("C1", True), ("C2", False), ("C3", True)])
        rel = m["relations"]
        self.assertEqual(rel["identical_to_parent"]["paraphrase"]["strict"], {"value": 2 / 3, "n": 2, "of": 3})
        self.assertEqual(rel["identical_to_parent"]["paraphrase"]["not_usable"], 1)
        self.assertEqual(rel["paraphrase_groups"]["identical_levels"]["strict"], {"value": 0.5, "n": 1, "of": 2})
        self.assertEqual(m["total"]["coverage"]["n"], N_CASES - 1)

    def test_missing_parsed_output_is_an_error(self):
        selection = dataset.select(self.ds, test_types=["paraphrase"])
        parsed = {i.test_id: parse.parse_text(render_grade(i.case), i.case["rubric"]) for i in selection.items}
        del parsed[selection.context_parent_ids[0]]
        with self.assertRaises(metrics.MetricsError):
            metrics.build_rows(self.ds, selection, parsed)


class AccuracyTest(Base):
    def test_error_sizes_and_within_one(self):
        # One error of +1: C2 max 4, draft minimal (1), graded partial (2), one level up.
        tid = mid("delta_04_ans01")
        m, _, _ = self.run_metrics({tid: self.reply(tid, {"C2": "partial"})})
        n = N_CRITERIA
        crit = m["criterion"]
        self.assertEqual(crit["strict_exact_agreement"]["n"], n - 1)
        self.assertEqual(crit["strict_within_one_level"]["n"], n)
        self.assertAlmostEqual(crit["mae_points"], 1 / n)
        self.assertAlmostEqual(crit["mean_signed_error_points"], 1 / n)
        self.assertLess(m["qwk"]["levels"], 1.0)
        self.assertLess(m["qwk"]["points_max_4"], 1.0)
        self.assertEqual(m["qwk"]["points_max_3"], 1.0)
        self.assertAlmostEqual(m["total"]["mean_signed_error_points"], 1 / N_CASES)
        # its fairness variant now differs from the model's own parent grade
        self.assertEqual(m["relations"]["identical_to_parent"]["fairness"]["strict"]["n"], 1)

        # Two levels off is not within one: C1 max 3, draft full (3), graded minimal (1).
        m, _, _ = self.run_metrics({ALL_FULL: self.reply(ALL_FULL, {"C1": "minimal"})})
        self.assertEqual(m["criterion"]["strict_within_one_level"]["n"], n - 1)
        self.assertLess(m["criterion"]["mean_signed_error_points"], 0)

        # An error of +1 on a 9-mark case and -1 on an 8-mark case: signed errors cancel, absolute ones don't.
        up, down = mid("gamma_03_ans02"), mid("delta_04_ans02")
        m, _, _ = self.run_metrics({up: self.reply(up, {"C1": "partial"}), down: self.reply(down, {"C1": "minimal"})})
        crit, total = m["criterion"], m["total"]
        self.assertAlmostEqual(crit["mae_points"], 2 / n)
        self.assertAlmostEqual(crit["mean_signed_error_points"], 0.0)
        self.assertAlmostEqual(total["mae_points"], 2 / N_CASES)
        self.assertAlmostEqual(total["mean_signed_error_points"], 0.0)
        self.assertAlmostEqual(total["mae_percent_of_max"], (100 / 9 + 100 / 8) / N_CASES)


class RelationTest(Base):
    def test_sensitivity_missed(self):
        variant, parent = mid("alpha_01_ans01_sens1"), mid("alpha_01_ans01")
        m, _, _ = self.run_metrics({variant: render_grade(self.cases[variant],
                                                         self.cases[parent]["draft_ground_truth"]["criteria"])})
        sens = m["relations"]["sensitivity"]
        for key in ("affected_and_total_drop", "any_total_drop"):
            self.assertEqual(sens[key]["strict"], {"value": 0.5, "n": 1, "of": 2}, key)

    def test_injection_inflates_grade(self):
        variant = mid("beta_02_ans01_inj1")   # draft 0/7, like its parent
        all_full = {c["id"]: "full" for c in self.cases[variant]["rubric"]}
        m, _, _ = self.run_metrics({variant: self.reply(variant, all_full)})
        inj = m["relations"]["robustness"]["injection"]
        self.assertEqual(inj["pass"]["strict"], {"value": 0.5, "n": 1, "of": 2})
        self.assertEqual(inj["inflated_vs_parent"], {"value": 0.5, "n": 1, "of": 2})
        self.assertEqual(m["relations"]["robustness"]["keyword_stuffing"]["pass"]["strict"]["value"], 1.0)


class SelectionRolesTest(Base):
    def test_context_parents_not_in_denominators(self):
        selection = dataset.select(self.ds, test_types=["paraphrase"])
        m, rows, _ = self.run_metrics(selection=selection)
        n = sum(len(c["rubric"]) for c in selection.selected)
        self.assertEqual(m["counts"]["selected_cases"], 3)
        self.assertEqual(m["counts"]["criteria"], n)
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["of"], n)
        self.assertEqual(m["format"]["format_compliant_cases"]["of"], 3)
        self.assertEqual(set(r["test_id"] for r in rows.cases), set(selection.selected_ids))
        self.assertEqual(m["counts"]["relation_pairs"], 3)
        self.assertEqual(m["counts"]["paraphrase_groups"], 2)
        self.assertEqual({r["parent_role"] for r in rows.pairs}, {dataset.CONTEXT_PARENT})

        # A parent that is selected itself is counted once.
        selection = dataset.select(self.ds, question_ids=[mid("alpha_01")])
        m, rows, _ = self.run_metrics(selection=selection)
        self.assertEqual(m["counts"]["selected_cases"], 6)
        self.assertEqual({r["parent_role"] for r in rows.pairs}, {dataset.SELECTED})

    def test_failed_context_parent_only_affects_relations(self):
        selection = dataset.select(self.ds, test_types=["paraphrase"])
        m, _, _ = self.run_metrics({mid("alpha_01_ans01"): "no grade"}, selection=selection)
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        self.assertEqual(m["format"]["format_compliant_cases"]["value"], 1.0)
        self.assertNotIn("parse_failure", m["format"]["case_status"])
        para = m["relations"]["identical_to_parent"]["paraphrase"]
        self.assertEqual((para["strict"]["n"], para["strict"]["of"], para["not_usable"]), (1, 3, 2))


class BreakdownTest(Base):
    def test_breakdowns(self):
        m, _, _ = self.run_metrics()
        for key in metrics.BREAKDOWNS:
            table = m["breakdowns"][key]
            self.assertEqual(sum(v["n_criteria"] for v in table.values()), N_CRITERIA, key)
        self.assertEqual(set(m["breakdowns"]["test_type"]), set(dataset.TEST_TYPES))
        self.assertEqual(set(m["breakdowns"]["gold_level"]), set(metrics.LEVEL_ORDER))
        self.assertEqual(set(m["breakdowns"]), {"topic", "test_type", "gold_level", "review_status"})
        self.assertEqual(sum(v["n_cases"] for v in m["breakdowns"]["topic"].values()), N_CASES)

        # A failure shows only under its own topic.
        m, _, _ = self.run_metrics({mid("gamma_03_ans02"): "no grade"})
        topics = m["breakdowns"]["topic"]
        self.assertLess(topics["automata_c"]["strict_exact_agreement"]["value"], 1.0)
        self.assertLess(topics["automata_c"]["format_compliant_cases"]["value"], 1.0)
        self.assertEqual(topics["induction_a"]["strict_exact_agreement"]["value"], 1.0)


class SummaryTest(Base):
    def summarize(self, replies=None, selection=None, n_boot=200, seed=0):
        selection = selection or dataset.select(self.ds)
        parsed = {i.test_id: parse.parse_text((replies or {}).get(i.test_id, render_grade(i.case)), i.case["rubric"])
                  for i in selection.items}
        return metrics.summarize(self.ds, selection, parsed, n_boot=n_boot, seed=seed)

    def test_summary_is_json_and_marked_provisional(self):
        s = self.summarize()
        json.dumps(s)
        self.assertTrue(s["labels"]["provisional"])
        self.assertIn("human-reviewed; provisional and not independently TA-verified or frozen", s["labels"]["note"])
        self.assertIn("confidence_flagging", s["not_yet_implemented"])  # documented, not dropped
        self.assertEqual(s["labels"]["dataset_sha256"], self.ds.sha256)
        self.assertEqual(s["selection"]["selected_count"], N_CASES)

    def test_bootstrap_intervals(self):
        ci = self.summarize()["headline_ci"]
        self.assertEqual(ci["strict_exact_agreement"]["ci95"], [1.0, 1.0])
        self.assertEqual(ci["strict_exact_agreement"]["resamples_used"], 200)

        # Deterministic, covers the estimate, and has real width because the failures are in only
        # some questions, so resampling the questions changes the result.
        replies = {mid("gamma_03_ans02"): "no grade", mid("delta_04_ans02"): "no grade"}
        a = self.summarize(replies)["headline_ci"]
        b = self.summarize(replies)["headline_ci"]
        self.assertEqual(a, b)
        lo, hi = a["strict_exact_agreement"]["ci95"]
        self.assertLessEqual(lo, a["strict_exact_agreement"]["estimate"])
        self.assertGreaterEqual(hi, a["strict_exact_agreement"]["estimate"])
        self.assertLess(lo, 1.0)
        self.assertLess(lo, hi)

        # One question has nothing to resample.
        ci = self.summarize(selection=dataset.select(self.ds, question_ids=[mid("alpha_01")]))["headline_ci"]
        self.assertIsNone(ci["strict_exact_agreement"]["ci95"])
        self.assertEqual(ci["strict_exact_agreement"]["estimate"], 1.0)


if __name__ == "__main__":
    unittest.main()
