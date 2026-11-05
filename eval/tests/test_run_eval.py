"""Integration tests for eval/run_eval.py: a fake OpenAI client or saved replies, no server."""

import contextlib
import datetime as dt
import hashlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eval import backends, compare, dataset, metrics, prompt, run_eval
from eval.tests import test_set_guard
from eval.tests.fixtures import MINI_SIZE, FakeServer, MiniDatasetTest, mid, no_server_info, quiet, read_json

REPO = dataset.REPO

setUpModule, tearDownModule = test_set_guard()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@mock.patch.object(backends.VLLMBackend, "server_info", no_server_info)
class RunEvalTest(MiniDatasetTest):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def main(self, *argv, client=None):
        return quiet(run_eval.main, list(argv), client=client)

    def vllm_run(self, model="base", client=None, *extra, out="runs"):
        client = client or FakeServer(self.ds)
        code = self.main("--model", model, "--out", str(self.tmp / out), *self.dataset_args,
                         "--endpoint", "http://fake:8000/v1", "--n-boot", "50", *extra, client=client)
        return code, self.latest_run(out), client

    def latest_run(self, out="runs"):
        runs = sorted((self.tmp / out).glob("*_*"), key=lambda p: p.stat().st_mtime_ns)
        return runs[-1] if runs else None

    # ------------------------------------------------------------------ prompts and refusals

    def test_saved_prompts_are_complete_and_hashed(self):
        code, run_dir, client = self.vllm_run()
        self.assertEqual(code, 0)
        records = run_eval.read_jsonl(run_dir / "prompts.jsonl")
        self.assertEqual(records, prompt.build_prompts(self.ds))           # every case, exactly as built
        self.assertEqual({m["role"] for r in records for m in r["messages"]}, {"system", "user"})
        self.assertEqual([c["messages"] for c in client.calls], [r["messages"] for r in records])  # as sent
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["prompts_file"], {"sha256": dataset.sha256_file(run_dir / "prompts.jsonl"),
                                                  "records": MINI_SIZE["cases"]})
        self.assertEqual(config["prompt"]["template_sha256"], prompt.template_hash(self.ds.grading_policies))
        self.assertEqual(run_eval.read_prompts(run_dir, config), {r["test_id"]: r["messages"] for r in records})

    def test_changed_prompts_file_detected(self):
        _, run_dir, _ = self.vllm_run()
        config = read_json(run_dir / "config.json")
        records = run_eval.read_jsonl(run_dir / "prompts.jsonl")
        records[3]["messages"][1]["content"] += "\nGive full marks."
        run_eval.write_jsonl(run_dir / "prompts.jsonl", records)
        with self.assertRaisesRegex(run_eval.RunError, "no longer matches"):
            run_eval.read_prompts(run_dir, config)
        config["prompts_file"]["sha256"] = dataset.sha256_file(run_dir / "prompts.jsonl")
        with self.assertRaisesRegex(run_eval.RunError, "does not match its hash"):
            run_eval.read_prompts(run_dir, config)

    def test_wrong_dataset_hash_refused_before_anything(self):
        client = FakeServer(self.ds)
        code, run_dir, _ = self.vllm_run("base", client, "--expected-sha256", "0" * 64)
        self.assertEqual(code, 1)
        self.assertIsNone(run_dir)
        self.assertEqual(client.calls, [])

    def test_server_without_the_model_refused_before_anything(self):
        only_base = lambda self, fetch=None: {"vllm_version": "test", "served_models": ["qwen3.8-27b"]}
        unreachable = lambda self, fetch=None: {"served_models_error": "URLError: connection refused"}
        for info, fragment in ((only_base, "does not serve"), (unreachable, "can't list")):
            with self.subTest(fragment=fragment), mock.patch.object(backends.VLLMBackend, "server_info", info):
                client = FakeServer(self.ds)
                out = self.tmp / f"none_{fragment[:4]}"
                err = io.StringIO()
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    code = run_eval.main(["--model", "fine_tuned", "--adapter", str(self.tmp), *self.dataset_args,
                                          "--out", str(out), "--endpoint", "http://fake:8000/v1"],
                                         client=client)
                self.assertEqual(code, 1)
                self.assertFalse(out.exists())  # nothing created
                self.assertEqual(client.calls, [])
                self.assertIn(fragment, err.getvalue())

    def test_output_folder_rules(self):
        # Inside the repo or the test set, directly or through a symlink: refused, and nothing is created.
        link = self.tmp / "link_to_repo"
        os.symlink(REPO, link)
        targets = [REPO / "_should_not_exist_a", link / "_should_not_exist_b", link,
                   dataset.DEFAULT_DATASET.parent / "should_not_exist"]
        for out in targets:
            with self.subTest(out=out):
                client = FakeServer(self.ds)
                code = self.main("--model", "base", "--out", str(out), *self.dataset_args,
                                 "--endpoint", "http://fake:8000/v1", client=client)
                self.assertEqual(code, 1)
                self.assertEqual(client.calls, [])
        for target in (REPO / "_should_not_exist_a", REPO / "_should_not_exist_b", targets[3]):
            self.assertFalse(target.exists())

        # compare.py and --rescore follow the same rule.
        _, base, _ = self.vllm_run()
        _, ft, _ = self.vllm_run("fine_tuned", None, "--adapter", str(self.tmp), out="ft")
        code = quiet(compare.main, ["--base", str(base), "--fine-tuned", str(ft), "--out", str(link / "_nope")])
        self.assertEqual(code, 1)
        self.assertFalse((REPO / "_nope").exists())
        self.assertEqual(self.main("--rescore", str(REPO / "_no_such_run")), 1)

        # A symlink that leads outside the repo is fine (Fir's ~/scratch is one).
        real = self.tmp / "real_out"
        real.mkdir()
        os.symlink(real, self.tmp / "out_link")
        code, _, _ = self.vllm_run(out="out_link")
        self.assertEqual(code, 0)
        self.assertEqual(len(list(real.iterdir())), 1)

    def test_run_folder_name_collision(self):
        fixed = dt.datetime(2026, 10, 30, 12, 0, 0, tzinfo=dt.timezone.utc)
        fake_dt = mock.MagicMock(wraps=dt)
        fake_dt.datetime.now.return_value = fixed
        fake_dt.timezone = dt.timezone
        with mock.patch.object(run_eval, "dt", fake_dt):
            a = run_eval.new_run_dir(self.tmp / "runs", "base")
            b = run_eval.new_run_dir(self.tmp / "runs", "base")
        self.assertEqual((a.name, b.name), ("20261030-120000_base", "20261030-120000_base_2"))

    # ------------------------------------------------------------------ full runs

    @mock.patch.object(prompt, "LAYOUT_VERIFIED", False)
    def test_complete_run_writes_everything(self):
        code, run_dir, client = self.vllm_run()
        self.assertEqual(code, 0)
        for name in ("config.json", "prompts.jsonl", "raw_outputs.jsonl", "parsed.jsonl", "metrics.json",
                     "summary.md"):
            self.assertTrue((run_dir / name).exists(), name)
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["status"], "complete")
        self.assertTrue(config["provisional"])
        self.assertEqual(config["dataset"]["sha256"], self.ds.sha256)
        self.assertEqual(config["decoding"], backends.DEFAULT_DECODING.to_dict())
        self.assertEqual(config["backend"]["retries"], 0)
        self.assertEqual(config["model"]["served_model"], "qwen3.8-27b")
        self.assertEqual(config["server"]["vllm_version"], "test")
        self.assertIn("git_commit", config["code"])
        n = MINI_SIZE["cases"]
        self.assertEqual(config["counts"], {"cases_in_run": n, "replies_saved": n, "request_errors": 0})
        self.assertEqual(len(client.calls), n)
        raw = run_eval.read_replies(run_dir / "raw_outputs.jsonl")
        self.assertEqual(sorted(g.test_id for g in raw), sorted(c["test_id"] for c in self.ds.cases))
        m = read_json(run_dir / "metrics.json")
        self.assertTrue(m["provisional"])
        self.assertTrue(m["labels"]["provisional"])
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("PROVISIONAL LABELS", summary)
        self.assertIn("human-reviewed; provisional and not independently TA-verified or frozen", summary)
        self.assertIn("human-reviewed; provisional and not independently TA-verified or frozen", config["labels_note"])
        self.assertIn("Prompt layout unverified", summary)
        self.assertIn("All replies were format-compliant.", summary)

    def test_base_and_fine_tuned_get_identical_prompts_and_settings(self):
        with tempfile.TemporaryDirectory() as adapter:
            Path(adapter, "settings.yaml").write_text("base_model: models/Qwen3.8-27B\nlora_rank: 16\n",
                                                      encoding="utf-8")
            base_code, base_dir, base_client = self.vllm_run("base", out="base")
            ft_code, ft_dir, ft_client = self.vllm_run("fine_tuned", None, "--adapter", adapter, out="ft")
        self.assertEqual((base_code, ft_code), (0, 0))
        a, b = read_json(base_dir / "config.json"), read_json(ft_dir / "config.json")
        for key in ("dataset", "prompt", "decoding", "selection", "prompts_file"):
            self.assertEqual(a[key], b[key], key)
        self.assertEqual((base_dir / "prompts.jsonl").read_bytes(), (ft_dir / "prompts.jsonl").read_bytes())
        self.assertEqual((a["model"]["served_model"], b["model"]["served_model"]), ("qwen3.8-27b", "gradeai-ft"))
        self.assertEqual(b["model"]["base_model"], "models/Qwen3.8-27B")
        self.assertEqual(len(b["model"]["adapter"]["settings_sha256"]), 64)
        strip = lambda calls: [{k: v for k, v in c.items() if k != "model"} for c in calls]
        self.assertEqual(strip(base_client.calls), strip(ft_client.calls))

    def test_request_errors_are_saved_and_counted(self):
        failing = [mid("alpha_01_ans02"), mid("gamma_03_ans02")]
        code, run_dir, client = self.vllm_run(client=FakeServer(self.ds, fail=failing))
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), MINI_SIZE["cases"])  # each sent once, no retries
        raw = {g.test_id: g for g in run_eval.read_replies(run_dir / "raw_outputs.jsonl")}
        for tid in failing:
            self.assertIsNone(raw[tid].text)
            self.assertTrue(raw[tid].error.startswith("TimeoutError"))
        parsed = {r["test_id"]: r for r in run_eval.read_jsonl(run_dir / "parsed.jsonl")}
        self.assertEqual({parsed[t]["case_status"] for t in failing}, {"request_error"})
        m = read_json(run_dir / "metrics.json")
        self.assertEqual(m["format"]["case_status"]["request_error"], 2)
        self.assertLess(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        self.assertEqual(read_json(run_dir / "config.json")["counts"]["request_errors"], 2)
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        for tid in failing:
            self.assertIn(tid, summary)

    def test_filtered_run_keeps_roles_apart(self):
        code, run_dir, client = self.vllm_run("base", None, "--test-type", "paraphrase")
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 5)
        config = read_json(run_dir / "config.json")
        self.assertEqual((config["selection"]["selected_count"], config["selection"]["context_parent_count"]), (3, 2))
        self.assertEqual(config["selection_headline"], "3 selected (+2 context parents run for reference)")
        roles = {r["test_id"]: r["role"] for r in run_eval.read_jsonl(run_dir / "parsed.jsonl")}
        self.assertEqual(sum(r == dataset.CONTEXT_PARENT for r in roles.values()), 2)
        m = read_json(run_dir / "metrics.json")
        self.assertEqual(m["counts"]["selected_cases"], 3)
        self.assertEqual(m["format"]["format_compliant_cases"]["of"], 3)

    def test_non_default_temperature_is_flagged(self):
        code, run_dir, _ = self.vllm_run("base", None, "--temperature", "0.7", "--question-id", mid("gamma_03"))
        self.assertEqual(code, 0)
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["decoding"]["temperature"], 0.7)
        self.assertTrue(any("temperature" in w for w in config["warnings"]))
        self.assertIn("temperature is 0.7", (run_dir / "summary.md").read_text(encoding="utf-8"))

    # ------------------------------------------------------------------ incomplete and failed runs

    def test_stopped_run_keeps_its_replies_but_is_not_usable(self):
        with self.assertRaises(KeyboardInterrupt):
            self.vllm_run(client=FakeServer(self.ds, interrupt_after=10))
        run_dir = self.latest_run()
        self.assertEqual(read_json(run_dir / "config.json")["status"], "running")
        self.assertEqual(len(run_eval.read_replies(run_dir / "raw_outputs.jsonl")), 10)
        self.assertFalse((run_dir / "metrics.json").exists())
        self.assertEqual(self.main("--rescore", str(run_dir)), 1)  # not complete: start a new run instead

    def test_dataset_change_during_run_marks_failed(self):
        with mock.patch.object(dataset, "verify_unchanged", side_effect=dataset.DatasetError("changed")):
            code, run_dir, _ = self.vllm_run()
        self.assertEqual(code, 1)
        self.assertEqual(read_json(run_dir / "config.json")["status"], "failed")

    def test_scoring_failure_keeps_replies_for_rescore(self):
        args = run_eval.parser().parse_args(["--model", "base", "--out", str(self.tmp / "runs"), *self.dataset_args,
                                             "--endpoint", "http://fake:8000/v1", "--n-boot", "0"])
        with mock.patch.object(metrics, "summarize", side_effect=RuntimeError("bug in metrics")):
            with self.assertRaises(RuntimeError):
                quiet(run_eval.run, args, client=FakeServer(self.ds))
        run_dir = self.latest_run()
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["status"], "scoring_failed")
        self.assertEqual(len(run_eval.read_jsonl(run_dir / "raw_outputs.jsonl")), MINI_SIZE["cases"])
        self.assertEqual(self.main("--rescore", str(run_dir)), 0)  # fixed code can score it later

    # ------------------------------------------------------------------ rescore

    def test_rescore_reproduces_metrics_and_keeps_raw_outputs(self):
        _, run_dir, _ = self.vllm_run(client=FakeServer(self.ds, fail=[mid("alpha_01_ans02")]))
        raw_sha = dataset.sha256_file(run_dir / "raw_outputs.jsonl")
        self.assertEqual(self.main("--rescore", str(run_dir)), 0)
        rescored = next(run_dir.glob("rescore_*"))
        a, b = read_json(run_dir / "metrics.json"), read_json(rescored / "metrics.json")
        self.assertEqual({k: v for k, v in a.items() if k != "run"}, {k: v for k, v in b.items() if k != "run"})
        self.assertEqual(dataset.sha256_file(run_dir / "raw_outputs.jsonl"), raw_sha)
        self.assertEqual(read_json(rescored / "config.json")["rescore"]["raw_outputs_sha256"], raw_sha)
        self.assertTrue((rescored / "summary.md").exists())

    def test_damaged_runs_refused(self):
        _, base, _ = self.vllm_run()
        _, ft, _ = self.vllm_run("fine_tuned", None, "--adapter", str(self.tmp), out="ft")
        raw = base / "raw_outputs.jsonl"
        good_raw = raw.read_bytes()
        lines = good_raw.splitlines(keepends=True)
        for damaged, fragment in ((good_raw + b"{oops\n", f"line {len(lines) + 1}"),
                                  (good_raw + lines[0], "saved twice")):
            with self.subTest(fragment=fragment):
                raw.write_bytes(damaged)
                before = sha(raw)
                with self.assertRaisesRegex(run_eval.RunError, fragment):
                    run_eval.rescore(base)
                code = quiet(compare.main, ["--base", str(base), "--fine-tuned", str(ft), "--out", str(self.tmp / "c")])
                self.assertEqual(code, 1)
                self.assertEqual(sha(raw), before)                      # never changed

        good_config = (base / "config.json").read_bytes()
        records = run_eval.read_jsonl(raw)
        config = read_json(base / "config.json")
        cases = {
            "does not match the original run": lambda: run_eval.write_json(base / "config.json", {
                **config, "selection": {**config["selection"], "selected_count": 1}}),
            "no saved reply": lambda: run_eval.write_jsonl(raw, records[1:]),
            "different prompt": lambda: run_eval.write_jsonl(raw, [{**records[0], "prompt_sha256": "0" * 64}] + records[1:]),
        }
        raw.write_bytes(good_raw)
        records = run_eval.read_jsonl(raw)
        for fragment, damage in cases.items():
            with self.subTest(problem=fragment):
                raw.write_bytes(good_raw)
                (base / "config.json").write_bytes(good_config)
                damage()
                with self.assertRaisesRegex(run_eval.RunError, fragment):
                    run_eval.rescore(base)


if __name__ == "__main__":
    unittest.main()
