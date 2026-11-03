"""Tests for eval/compare.py, on run folders made with a fake server (no model is called)."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eval import backends, compare, dataset, prompt, run_eval
from eval.tests import test_set_guard
from eval.tests.fixtures import (MINI_SIZE, FakeServer, MiniDatasetTest, mid, no_server_info, quiet, read_json,
                                 render_grade, with_levels)

setUpModule, tearDownModule = test_set_guard()

# One case from each question, graded wrongly in the "worse" run.
WRONG = [mid("alpha_01_ans02"), mid("beta_02_ans02"), mid("gamma_03_ans02"), mid("delta_04_ans02")]
UNPARSEABLE = mid("alpha_01_ans01_para2")
INJECTED = mid("beta_02_ans01_inj1")   # draft 0/7; the worse run gives full marks


@mock.patch.object(backends.VLLMBackend, "server_info", no_server_info)
class CompareTest(MiniDatasetTest):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.adapter = self.tmp / "adapter"
        self.adapter.mkdir()
        (self.adapter / "settings.yaml").write_text("base_model: models/Qwen3.8-27B\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def reply(self, tid, changes):
        return render_grade(self.cases[tid], with_levels(self.cases[tid], changes))

    def worse_replies(self):
        replies = {}
        for tid in WRONG:
            g = self.cases[tid]["draft_ground_truth"]["criteria"][0]
            replies[tid] = self.reply(tid, {g["criterion_id"]: "minimal" if g["level"] == "full" else "full"})
        replies[UNPARSEABLE] = "I would give this about half marks."
        replies[INJECTED] = self.reply(INJECTED, {c["id"]: "full" for c in self.cases[INJECTED]["rubric"]})
        return replies

    def make_run(self, model, replies=None, *extra, interrupt_after=None):
        out = self.tmp / "runs"
        before = set(out.glob("*")) if out.exists() else set()
        args = ["--model", model, "--out", str(out), *self.dataset_args,
                "--endpoint", "http://fake:8000/v1", "--n-boot", "0", "--base-model" if model == "base" else "--adapter",
                "models/Qwen3.8-27B" if model == "base" else str(self.adapter), *extra]
        try:
            quiet(run_eval.main, args, client=FakeServer(self.ds, replies, interrupt_after=interrupt_after))
        except KeyboardInterrupt:
            pass  # a run that stopped part way: its folder stays, marked "running"
        (new,) = set(out.glob("*")) - before
        return new

    def compare(self, base, ft, n_boot=300):
        return compare.compare(base, ft, n_boot=n_boot, seed=0)

    def edit_config(self, run_dir, change):
        config = read_json(run_dir / run_eval.CONFIG)
        change(config)
        run_eval.write_json(run_dir / run_eval.CONFIG, config)

    # ------------------------------------------------------------------ directions and verdicts

    def test_direction_and_verdicts(self):
        r = self.compare(self.make_run("base", self.worse_replies()), self.make_run("fine_tuned"))
        self.assertTrue(r["provisional"])
        h = r["headline"]
        for name in ("strict_exact_agreement", "coverage", "format_compliance", "robustness_pass"):
            self.assertEqual(h[name]["verdict"], "improved", name)
            self.assertGreater(h[name]["estimate"], 0, name)
        self.assertTrue(h["strict_exact_agreement"]["ci_excludes_zero"])
        self.assertGreater(h["strict_exact_agreement"]["ci95"][0], 0)
        # lower is better: MAE goes down, and that is an improvement
        self.assertLess(h["mae_points"]["estimate"], 0)
        self.assertEqual(h["mae_points"]["verdict"], "improved")
        self.assertEqual(h["mean_signed_error_points"]["verdict"], "-")
        # parse failures and injection success are reported for both models
        mb, mf = r["metrics"]["base"], r["metrics"]["fine_tuned"]
        self.assertEqual((mb["format"]["case_status"].get("parse_failure"), mf["format"]["case_status"].get("parse_failure")),
                         (1, None))
        self.assertEqual((mb["relations"]["robustness"]["injection"]["inflated_vs_parent"]["n"],
                          mf["relations"]["robustness"]["injection"]["inflated_vs_parent"]["n"]), (1, 0))
        po = r["paired_criterion_outcomes"]
        self.assertEqual(po["base_only_correct"], 0)
        wrong = len(WRONG) + len(self.cases[UNPARSEABLE]["rubric"]) + len(self.cases[INJECTED]["rubric"])
        self.assertEqual(po["fine_tuned_only_correct"], wrong)
        self.assertEqual(sum(po[k] for k in ("both_correct", "base_only_correct", "fine_tuned_only_correct",
                                             "neither_correct")), MINI_SIZE["criteria"])
        self.assertEqual(sorted(po["cases_with_changes"]), sorted(WRONG + [UNPARSEABLE, INJECTED]))

        r = self.compare(self.make_run("base"), self.make_run("fine_tuned", self.worse_replies()))
        h = r["headline"]
        self.assertEqual(h["strict_exact_agreement"]["verdict"], "regressed")
        self.assertLess(h["strict_exact_agreement"]["ci95"][1], 0)
        self.assertGreater(h["mae_points"]["estimate"], 0)
        self.assertEqual(h["mae_points"]["verdict"], "regressed")
        self.assertEqual(h["format_compliance"]["verdict"], "regressed")
        self.assertEqual(h["robustness_pass"]["verdict"], "regressed")
        self.assertGreater(r["paired_criterion_outcomes"]["base_only_correct"], 0)

    def test_signed_error_judged_by_distance_from_zero(self):
        first, second = mid("gamma_03_ans02"), mid("delta_04_ans02")
        harsh = {first: self.reply(first, {"C1": "none"}), second: self.reply(second, {"C2": "none"})}  # two errors of -1
        lenient = {first: self.reply(first, {"C1": "partial"})}                                         # one error of +1
        r = self.compare(self.make_run("base", harsh), self.make_run("fine_tuned", lenient))
        signed = r["headline"]["mean_signed_error_points"]
        self.assertLess(signed["base"], 0)
        self.assertGreater(signed["fine_tuned"], 0)
        self.assertEqual(signed["verdict"], "-")
        self.assertEqual(r["headline"]["abs_mean_signed_error_points"]["verdict"], "improved")

    def test_identical_runs_unchanged(self):
        r = self.compare(self.make_run("base"), self.make_run("fine_tuned"))
        self.assertEqual({e["verdict"] for e in r["headline"].values()} - {"-", "n/a"}, {"unchanged"})
        for name, e in r["headline"].items():
            if e["estimate"] is not None:
                self.assertEqual(e["estimate"], 0, name)
                self.assertFalse(e["ci_excludes_zero"], name)
        self.assertEqual(r["paired_criterion_outcomes"]["both_correct"], MINI_SIZE["criteria"])

    def test_judge(self):
        self.assertEqual(compare.judge(compare.HIGHER, 0.8, 0.9), "improved")
        self.assertEqual(compare.judge(compare.LOWER, 0.2, 0.1), "improved")
        self.assertEqual(compare.judge(compare.LOWER, 0.1, 0.2), "regressed")
        self.assertEqual(compare.judge(compare.HIGHER, 0.5, 0.5), "unchanged")
        self.assertEqual(compare.judge(compare.HIGHER, None, 0.5), "n/a")
        self.assertEqual(compare.judge(compare.NEUTRAL, 1, 2), "-")
        self.assertEqual(compare.HEADLINE_DIRECTION["mae_points"], compare.LOWER)

    # ------------------------------------------------------------------ refusals

    def assert_refused(self, base, ft, *fragments):
        with self.assertRaises(compare.CompareError) as ctx:
            self.compare(base, ft)
        for fragment in fragments:
            self.assertIn(fragment, str(ctx.exception))

    def test_mismatched_runs_refused(self):
        base = self.make_run("base")
        self.assert_refused(base, self.make_run("fine_tuned", None, "--test-type", "paraphrase"),
                            "filters", "selected cases", "context parents")
        self.assert_refused(base, self.make_run("fine_tuned", None, "--max-tokens", "1000"), "decoding")
        # All problems are listed together.
        self.assert_refused(base, self.make_run("fine_tuned", None, "--max-tokens", "1000",
                                                "--question-id", mid("alpha_01")),
                            "decoding", "filters")
        # The flag changes the template hash but not the prompt text, so only the template differs.
        with mock.patch.object(prompt, "LAYOUT_VERIFIED", not prompt.LAYOUT_VERIFIED):
            ft = self.make_run("fine_tuned")
        self.assert_refused(base, ft, "prompt template")

        ft = self.make_run("fine_tuned")
        self.edit_config(ft, lambda c: c["dataset"].__setitem__("sha256", "0" * 64))
        self.assert_refused(base, ft, "dataset SHA-256")

        (self.adapter / "settings.yaml").write_text("base_model: models/Other-8B\n", encoding="utf-8")
        self.assert_refused(base, self.make_run("fine_tuned"), "adapter was trained on")

    def test_wrong_runs_refused(self):
        a, b = self.make_run("base"), self.make_run("base")
        self.assert_refused(a, self.make_run("fine_tuned", interrupt_after=5), "not complete")
        self.assert_refused(a, b, "--fine-tuned run is a base run", "served model")
        ft = self.make_run("fine_tuned")
        self.assert_refused(ft, a, "--base run is a fine_tuned run")
        quiet(run_eval.main, ["--rescore", str(ft)])
        self.assert_refused(a, next(ft.glob("rescore_*")), "rescore folder")
        with self.assertRaisesRegex(compare.CompareError, "not a run folder"):
            compare.load_run(self.tmp)

    def test_tampered_runs_refused(self):
        base = self.make_run("base")

        ft = self.make_run("fine_tuned")
        with open(ft / run_eval.PROMPTS, "a", encoding="utf-8") as f:
            f.write("\n")
        self.assert_refused(base, ft, "no longer matches its config")

        # A different system message, even with consistent hashes.
        ft = self.make_run("fine_tuned")
        records = run_eval.read_jsonl(ft / run_eval.PROMPTS)
        records[0]["messages"][0]["content"] += " Be lenient."
        records[0]["prompt_sha256"] = prompt.messages_sha256(records[0]["messages"])
        run_eval.write_jsonl(ft / run_eval.PROMPTS, records)
        self.edit_config(ft, lambda c: c["prompts_file"].__setitem__("sha256", dataset.sha256_file(ft / run_eval.PROMPTS)))
        self.assert_refused(base, ft, "prompts file")

        # Prompts are compared in full.
        same = {"a": [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]}
        compare.check_same_prompts(same, copy.deepcopy(same))
        for other in ({"a": [{"role": "system", "content": "S!"}, {"role": "user", "content": "U"}]},
                      {"a": same["a"], "b": same["a"]}, {}):
            with self.assertRaisesRegex(compare.CompareError, "sent different prompts"):
                compare.check_same_prompts(same, other)

        # A reply made from another prompt.
        ft = self.make_run("fine_tuned")
        records = run_eval.read_jsonl(ft / run_eval.RAW)
        records[0]["prompt_sha256"] = "0" * 64
        run_eval.write_jsonl(ft / run_eval.RAW, records)
        with self.assertRaisesRegex(compare.CompareError, "different prompt"):
            self.compare(base, ft)

    # ------------------------------------------------------------------ warnings and output

    def test_stale_saved_metrics_warned_and_ignored(self):
        base, ft = self.make_run("base"), self.make_run("fine_tuned")
        saved = read_json(base / run_eval.METRICS)
        saved["criterion"]["strict_exact_agreement"]["value"] = 0.5
        run_eval.write_json(base / run_eval.METRICS, saved)
        r = self.compare(base, ft)
        self.assertTrue(any("saved metrics.json differs" in w for w in r["warnings"]))
        self.assertEqual(r["metrics"]["base"]["criterion"]["strict_exact_agreement"]["value"], 1.0)

    def test_warnings(self):
        base, ft = self.make_run("base"), self.make_run("fine_tuned")
        self.edit_config(base, lambda c: c["model"].__setitem__("base_model", None))
        self.edit_config(base, lambda c: c["prompt"].__setitem__("layout_verified", False))
        self.edit_config(ft, lambda c: c["code"].__setitem__("git_commit", "0" * 40))
        self.edit_config(ft, lambda c: c["server"].__setitem__("vllm_version", "other"))
        warnings = self.compare(base, ft, n_boot=0)["warnings"]
        for fragment in ("does not record its base model", "different code", "different vLLM versions", "layout"):
            self.assertTrue(any(fragment in w for w in warnings), fragment)

        self.edit_config(base, lambda c: c["prompt"].__setitem__("layout_verified", True))
        self.assertFalse(any("layout" in w for w in self.compare(base, ft, n_boot=0)["warnings"]))

    @mock.patch.object(prompt, "LAYOUT_VERIFIED", False)
    def test_cli_writes_report(self):
        base, ft = self.make_run("base", self.worse_replies()), self.make_run("fine_tuned")
        out = self.tmp / "compare"
        code = quiet(compare.main, ["--base", str(base), "--fine-tuned", str(ft), "--out", str(out), "--n-boot", "100"])
        self.assertEqual(code, 0)
        (folder,) = out.iterdir()
        result = read_json(folder / "compare.json")
        self.assertTrue(result["provisional"])
        self.assertEqual(result["shared"]["dataset"]["sha256"], self.ds.sha256)
        md = (folder / "compare.md").read_text(encoding="utf-8")
        for text in ("PROVISIONAL LABELS", "Prompt layout unverified", "Coverage and parsing failures",
                     "Cases: parse_failure", "Criterion coverage", "Correct only for fine-tuned",
                     "### By topic", "### By test type", "fairness_identical", "Not yet implemented"):
            self.assertIn(text, md)

    def test_cli_refusals_write_nothing(self):
        base, ft = self.make_run("base"), self.make_run("fine_tuned", interrupt_after=3)
        out = self.tmp / "compare"
        code = quiet(compare.main, ["--base", str(base), "--fine-tuned", str(ft), "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertFalse(out.exists() and any(out.iterdir()))

        ft = self.make_run("fine_tuned")
        target = dataset.DEFAULT_DATASET.parent / "should_not_exist"
        self.assertEqual(quiet(compare.main, ["--base", str(base), "--fine-tuned", str(ft), "--out", str(target)]), 1)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
