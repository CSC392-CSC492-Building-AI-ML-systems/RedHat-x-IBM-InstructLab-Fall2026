"""Group B v4 (test_set/groupB_v4_101.json), the Group B default: loading by its pinned hash, its
contents, prompts that are identical to v3's for the 60 carried-over cases, scoring without
review_status, and labels notes that do not call the 41 added cases human-reviewed. Group B v3
(test_set/groupB_60_draft.json) is still run, re-scored and labelled as before when chosen by its file.
Nothing here runs a model: replies come from a fake client that grades with the labels.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eval import backends, compare, dataset, metrics, parse, prompt, report, run_eval
from eval.tests import test_set_guard
from eval.tests.fixtures import FakeServer, no_server_info, quiet, read_json, render_grade
from eval.tests.test_group_a import (GROUP_B_PROMPT_DESCRIBE, GROUP_B_PROMPTS_SHA256, GROUP_B_TEMPLATE_SHA256,
                                     canonical_sha256)

setUpModule, tearDownModule = test_set_guard()

V4 = dataset.GROUP_B_V4_DATASET
V3 = dataset.GROUP_B_V3_DATASET


def load_v4():
    return dataset.load_group("B", V4)


def load_v3():
    return dataset.load_group("B", V3)


class V4DatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v3 = load_v3()
        cls.v4 = load_v4()

    def test_pinned_hash(self):
        self.assertEqual(self.v4.sha256, dataset.GROUP_B_V4_SHA256)
        self.assertEqual(dataset.sha256_file(V4), dataset.GROUP_B_V4_SHA256)
        self.assertEqual(self.v4.group.name, "B")
        # Any other hash is refused, including v3's.
        with self.assertRaisesRegex(dataset.DatasetError, "expected"):
            dataset.load_group("B", V4, "0" * 64)
        with self.assertRaisesRegex(dataset.DatasetError, "expected"):
            dataset.load(V4, dataset.GROUP_B_V3_SHA256)
        with self.assertRaisesRegex(dataset.DatasetError, "not Group A"):
            dataset.load_group("A", V4)

    def test_v4_is_the_default(self):
        self.assertEqual((dataset.DEFAULT_DATASET, dataset.EXPECTED_SHA256), (V4, dataset.GROUP_B_V4_SHA256))
        self.assertEqual((dataset.GROUPS["B"].default_path, dataset.GROUPS["B"].default_sha256),
                         (V4, dataset.GROUP_B_V4_SHA256))
        for ds in (dataset.load(), dataset.load_group("B"), run_eval.load_dataset(None, None, None),
                   run_eval.load_dataset("B", None, None), run_eval.load_dataset(None, str(V4), None),
                   run_eval.load_dataset("B", str(V4), dataset.GROUP_B_V4_SHA256)):
            self.assertEqual((ds.sha256, len(ds.cases), ds.path), (dataset.GROUP_B_V4_SHA256, 101, V4))

    def test_v3_by_its_file(self):
        # v3 keeps its hash (pinned), its 60 cases and its review_status field.
        self.assertEqual(dataset.sha256_file(V3), dataset.GROUP_B_V3_SHA256)
        self.assertEqual(dataset.PINNED_SHA256[V3], dataset.GROUP_B_V3_SHA256)
        for ds in (self.v3, run_eval.load_dataset(None, str(V3), None),
                   run_eval.load_dataset("B", str(V3), dataset.GROUP_B_V3_SHA256),
                   dataset.load(V3, dataset.GROUP_B_V3_SHA256)):
            self.assertEqual((ds.sha256, len(ds.cases), ds.path), (dataset.GROUP_B_V3_SHA256, 60, V3))
        self.assertTrue(all(c["review_status"] == "human_reviewed" for c in self.v3.cases))
        self.assertEqual(dataset.check_structure(self.v3), [])
        # The default hash is v4's, so v3 is refused without its own.
        with self.assertRaisesRegex(dataset.DatasetError, "expected"):
            dataset.load(V3)
        with self.assertRaisesRegex(dataset.DatasetError, "expected"):
            dataset.load_group("B", V3, dataset.GROUP_B_V4_SHA256)

    def test_contents(self):
        cases = self.v4.cases
        self.assertEqual(dataset.check_structure(self.v4), [])
        self.assertEqual((len(cases), self.v4.data["case_count"]), (101, 101))
        self.assertEqual(len({c["question_id"] for c in cases}), 32)
        self.assertEqual(len({c["test_id"] for c in cases}), 101)
        # review_status is gone everywhere; label_source keeps each case's provenance.
        self.assertFalse(any("review_status" in c for c in cases))
        self.assertNotIn("review_status", self.v4.held_out_fields)
        self.assertNotIn("review_status", self.v4.data["field_notes"])
        self.assertTrue(all(c["label_source"] for c in cases))
        added = [c for c in cases[60:]]
        self.assertTrue(all("not independently verified by a human" in c["label_source"] for c in added))
        self.assertNotIn("human review complete", self.v4.status)
        self.assertIn("not been independently verified by a human", self.v4.status)
        self.assertIn("not frozen, not team-approved", self.v4.status)

    def test_no_human_review_claims(self):
        texts = [self.v4.status, *self.v4.data["field_notes"].values(), *(c["label_source"] for c in self.v4.cases),
                 dataset.GROUP_B_V4_LABELS_NOTE, report.PROVISIONAL_B_V4]
        for text in texts:
            for claim in ("human-reviewed", "human_reviewed", "human review", "reviewed values", "reviewed draft"):
                self.assertNotIn(claim, text.lower())

    def test_first_60_cases_are_v3(self):
        # Only the review metadata differs: review_status is gone and label_source no longer claims a review.
        for old, new in zip(self.v3.cases, self.v4.cases[:60]):
            self.assertEqual({k: v for k, v in old.items() if k not in ("review_status", "label_source")},
                             {k: v for k, v in new.items() if k != "label_source"})
            self.assertIn("carried over unchanged from draft-v3", new["label_source"])
        self.assertEqual(self.v4.grading_policies, self.v3.grading_policies)
        self.assertEqual(self.v4.grader_visible_fields, self.v3.grader_visible_fields)

    def test_prompts_of_the_60_unchanged(self):
        records = prompt.build_prompts(self.v4)
        self.assertEqual(canonical_sha256(records[:60]), GROUP_B_PROMPTS_SHA256)
        self.assertEqual(records[:60], prompt.build_prompts(self.v3))
        self.assertEqual(prompt.dataset_template_hash(self.v4), GROUP_B_TEMPLATE_SHA256)
        self.assertEqual(prompt.describe(self.v4), GROUP_B_PROMPT_DESCRIBE)
        for case in self.v4.cases:
            prompt.check_no_leak(prompt.messages_for_case(self.v4, case), case, self.v4.general_rules(case))

    def test_labels_notes(self):
        v4_info, v3_info = self.v4.describe(), self.v3.describe()
        self.assertNotIn("group", v4_info)  # same config shape as Group B v3
        self.assertEqual(dataset.labels_note(v4_info), dataset.GROUP_B_V4_LABELS_NOTE)
        self.assertEqual(report.provisional_banner(v4_info), report.PROVISIONAL_B_V4)
        for text in (dataset.GROUP_B_V4_LABELS_NOTE, report.PROVISIONAL_B_V4):
            self.assertIn("not independently verified by a human", text)
        # v3, configs without a hash, and Group A keep their notes.
        self.assertEqual(dataset.labels_note(v3_info), dataset.GROUPS["B"].labels_note)
        self.assertEqual(dataset.labels_note({}), dataset.GROUPS["B"].labels_note)
        self.assertEqual(report.provisional_banner(v3_info), report.PROVISIONAL)
        self.assertEqual(report.provisional_banner({"group": "A"}), report.PROVISIONAL_A)


class V4MetricsTest(unittest.TestCase):
    def score(self, ds, replies=None):
        selection = dataset.select(ds)
        parsed = {i.test_id: parse.parse_text((replies or {}).get(i.test_id, render_grade(i.case)),
                                              i.case["rubric"], test_id=i.test_id) for i in selection.items}
        return metrics.summarize(ds, selection, parsed, n_boot=20)

    def test_scoring_without_review_status(self):
        m = self.score(load_v4())
        self.assertEqual(set(m["breakdowns"]), {"topic", "test_type", "gold_level"})
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        self.assertEqual(m["counts"]["selected_cases"], 101)
        self.assertEqual(m["counts"]["questions"], 32)
        self.assertEqual(m["labels"]["note"], dataset.GROUP_B_V4_LABELS_NOTE)
        for name in ("paraphrase", "fairness", "robustness"):
            self.assertEqual(m["relations"]["identical_to_parent"][name]["strict"]["value"], 1.0, name)
        self.assertEqual(m["relations"]["sensitivity"]["affected_and_total_drop"]["strict"]["value"], 1.0)

    def test_v3_keeps_its_review_status_breakdown(self):
        m = self.score(load_v3())
        self.assertEqual(set(m["breakdowns"]), set(metrics.BREAKDOWNS))
        self.assertEqual(set(m["breakdowns"]["review_status"]), {"human_reviewed"})
        self.assertEqual(m["labels"]["note"], "AI-drafted labels, human-reviewed; provisional and not independently "
                                              "TA-verified or frozen. Not reportable answer-key results.")


@mock.patch.object(backends.VLLMBackend, "server_info", no_server_info)
class V4RunTest(unittest.TestCase):
    """run_eval and rescore on v4 with a fake client that grades with the labels."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_round_trip(self):
        ds = load_v4()
        client = FakeServer(ds)
        code = quiet(run_eval.main, ["--model", "base", "--out", str(self.tmp), "--endpoint", "http://fake:8000/v1",
                                     "--n-boot", "20", "--dataset", str(V4)], client=client)
        self.assertEqual(code, 0)
        (run_dir,) = self.tmp.glob("*_base")
        self.assertEqual(len(client.calls), 101)
        config = read_json(run_dir / "config.json")
        self.assertEqual((config["dataset"]["sha256"], config["dataset"]["case_count"]),
                         (dataset.GROUP_B_V4_SHA256, 101))
        self.assertEqual(config["labels_note"], dataset.GROUP_B_V4_LABELS_NOTE)
        self.assertEqual(config["prompt"], GROUP_B_PROMPT_DESCRIBE)
        m = read_json(run_dir / "metrics.json")
        self.assertEqual(m["note"], dataset.GROUP_B_V4_LABELS_NOTE)
        self.assertNotIn("review_status", m["breakdowns"])
        self.assertEqual(m["criterion"]["strict_exact_agreement"]["value"], 1.0)
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn(report.PROVISIONAL_B_V4, summary)
        self.assertNotIn(report.PROVISIONAL, summary)
        self.assertNotIn("By review status", summary)
        out = quiet(run_eval.rescore, run_dir)
        self.assertEqual(read_json(out / "metrics.json")["criterion"], m["criterion"])

    def run_model(self, model, *args, out, client):
        code = quiet(run_eval.main, ["--model", model, "--out", str(self.tmp / out), "--endpoint",
                                     "http://fake:8000/v1", "--n-boot", "20", *args], client=client)
        self.assertEqual(code, 0)
        (run_dir,) = (self.tmp / out).glob("*_*")
        return run_dir

    def test_default_run_is_v4(self):
        question = "csc236_B_dfa_25"  # only in v4
        run_dir = self.run_model("base", "--question-id", question, out="default", client=FakeServer(load_v4()))
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["dataset"], load_v4().describe())
        self.assertEqual(config["labels_note"], dataset.GROUP_B_V4_LABELS_NOTE)
        self.assertIn(report.PROVISIONAL_B_V4, (run_dir / "summary.md").read_text(encoding="utf-8"))

    def test_v3_run_rescore_and_compare(self):
        # A v3 run made now has the config a run made while v3 was the default had, and is re-scored
        # against v3 (the file and hash in its config), with v3's notes and its review_status breakdown.
        v3 = load_v3()
        question = v3.cases[0]["question_id"]
        run_dir = self.run_model("base", "--dataset", str(V3), "--question-id", question, out="v3",
                                 client=FakeServer(v3))
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["dataset"], v3.describe())
        self.assertNotIn("group", config["dataset"])
        self.assertEqual(config["labels_note"], dataset.GROUPS["B"].labels_note)
        self.assertEqual(config["prompt"], GROUP_B_PROMPT_DESCRIBE)
        m = read_json(run_dir / "metrics.json")
        self.assertEqual(m["labels"]["dataset_sha256"], dataset.GROUP_B_V3_SHA256)
        self.assertEqual(m["labels"]["note"], "AI-drafted labels, human-reviewed; provisional and not independently "
                                              "TA-verified or frozen. Not reportable answer-key results.")
        self.assertIn("review_status", m["breakdowns"])
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn(report.PROVISIONAL, summary)
        self.assertNotIn(report.PROVISIONAL_B_V4, summary)
        out = quiet(run_eval.rescore, run_dir)
        rescored = read_json(out / "metrics.json")
        self.assertEqual(read_json(out / "config.json")["dataset"], config["dataset"])
        for key in ("criterion", "labels", "breakdowns", "relations", "counts"):
            self.assertEqual(rescored[key], m[key], key)
        self.assertEqual((out / "summary.md").read_text(encoding="utf-8").split("## Run")[0], summary.split("## Run")[0])

        # The same question on v4 gets byte-identical prompts, but runs on different files can't be compared.
        v4_dir = self.run_model("fine_tuned", "--question-id", question, out="v4", client=FakeServer(load_v4()))
        self.assertEqual(run_eval.read_jsonl(v4_dir / "prompts.jsonl"), run_eval.read_jsonl(run_dir / "prompts.jsonl"))
        with self.assertRaisesRegex(compare.CompareError, "dataset"):
            compare.compare(run_dir, v4_dir, n_boot=10)


if __name__ == "__main__":
    unittest.main()
