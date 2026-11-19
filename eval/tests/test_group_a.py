"""Group A support, and checks that Group B behaves exactly as before.

Group A (test_set/groupA_40_final.json) shows each case's own general_rules in the prompt; Group B
keeps its dataset-level grading_policies. Nothing here runs a model: replies come from a fake client
that grades with the labels.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from eval import backends, compare, dataset, parse, prompt, run_eval
from eval.tests import test_set_guard
from eval.tests.fixtures import FakeServer, no_server_info, quiet, read_json, render_grade

setUpModule, tearDownModule = test_set_guard()

# Group B before Group A support was added, built with the unchanged default loader: the SHA-256 of
# all 60 prompt records (canonical JSON), the template hash and the prompt description.
GROUP_B_PROMPTS_SHA256 = "29180ba52b0d7fe28e5a126648f9715d61f1c7bdb9cefa09d6ccb5e19d5da58a"
GROUP_B_TEMPLATE_SHA256 = "0d90dc78c10070c326f868c24958c4ac31ab598a303dc80ca02ef314df431890"
GROUP_B_PROMPT_DESCRIBE = {"template_version": "eval-prompt-v3", "template_sha256": GROUP_B_TEMPLATE_SHA256,
                           "layout_verified": False, "general_rules_source": "dataset grading_policies",
                           "general_rules_count": 4}


def canonical_sha256(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def user_text(messages):
    return next(m["content"] for m in messages if m["role"] == "user")


class GroupBUnchangedTest(unittest.TestCase):
    """Group B v3 prompts and configs are byte for byte what they were before Group A support. v3 is no
    longer the default (v4 is; see test_group_b_v4), so it is loaded by its file."""

    @classmethod
    def setUpClass(cls):
        cls.ds = dataset.load_group("B", dataset.GROUP_B_V3_DATASET)

    def test_default_load_is_group_b(self):
        self.assertEqual((self.ds.group.name, self.ds.sha256, len(self.ds.cases)),
                         ("B", dataset.GROUP_B_V3_SHA256, 60))
        self.assertEqual(dataset.load(dataset.GROUP_B_V3_DATASET, dataset.GROUP_B_V3_SHA256).sha256, self.ds.sha256)
        self.assertEqual(dataset.load_group("B").group.name, "B")
        self.assertNotIn("group", self.ds.describe())  # Group B run configs keep their old shape
        self.assertEqual(dataset.check_structure(self.ds), [])

    def test_prompts_identical_to_before(self):
        self.assertEqual(canonical_sha256(prompt.build_prompts(self.ds)), GROUP_B_PROMPTS_SHA256)
        self.assertEqual(prompt.template_hash(self.ds.grading_policies), GROUP_B_TEMPLATE_SHA256)
        self.assertEqual(prompt.dataset_template_hash(self.ds), GROUP_B_TEMPLATE_SHA256)
        self.assertEqual(prompt.describe(self.ds), GROUP_B_PROMPT_DESCRIBE)

    def test_every_case_uses_the_dataset_policies(self):
        for case in self.ds.cases:
            self.assertEqual(self.ds.general_rules(case), self.ds.grading_policies)
            self.assertEqual(prompt.messages_for_case(self.ds, case),
                             prompt.build_messages(dataset.grader_input(case), self.ds.grading_policies))

    def test_labels_note_unchanged(self):
        self.assertEqual(run_eval.PROVISIONAL_NOTE, dataset.labels_note(self.ds.describe()))
        self.assertIn("Group B AI-drafted labels", run_eval.PROVISIONAL_NOTE)


class GroupALoadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = dataset.load_group("A")
        cls.raw = json.loads(dataset.GROUP_A_DATASET.read_text(encoding="utf-8"))

    def write(self, data) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "groupA.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def mutated(self, change):
        data = json.loads(json.dumps(self.raw))
        change(data)
        return self.write(data)

    def test_real_file(self):
        ds = self.ds
        self.assertEqual((ds.group.name, ds.sha256, len(ds.cases)), ("A", dataset.GROUP_A_SHA256, 40))
        self.assertEqual(ds.describe()["group"], "A")
        self.assertEqual(dataset.check_structure(ds), [])
        self.assertNotIn("grading_policies", ds.data)
        self.assertEqual({c["test_type"] for c in ds.cases}, {"original"})
        sel = dataset.select(ds)
        self.assertEqual((len(sel.selected_ids), sel.context_parent_ids), (40, []))
        self.assertEqual(len(dataset.select(ds, topics=["regex"]).selected_ids), 5)
        with self.assertRaises(KeyError):
            ds.grading_policies  # noqa: B018 - Group A has no dataset-level rules

    def test_wrong_file_or_group_refused(self):
        with self.assertRaisesRegex(dataset.DatasetError, "SHA-256"):
            dataset.load_group("A", dataset.DEFAULT_DATASET, dataset.GROUP_A_SHA256)
        for path in (dataset.GROUP_B_V4_DATASET, dataset.GROUP_B_V3_DATASET):  # pinned: their own hash, then the group
            with self.assertRaisesRegex(dataset.DatasetError, "is a Group B test set, not Group A"):
                dataset.load_group("A", path)
        with self.assertRaisesRegex(dataset.DatasetError, "is a Group B test set, not Group A"):
            dataset.load_group("A", dataset.DEFAULT_DATASET, expected_sha256=None)
        with self.assertRaisesRegex(dataset.DatasetError, "is a Group A test set, not Group B"):
            dataset.load_group("B", dataset.GROUP_A_DATASET, expected_sha256=None)

    def test_bad_group_a_files_refused(self):
        def add_policies(d):
            d["grading_policies"] = ["One rule for every case."]

        def empty_rules(d):
            d["test_cases"][3]["general_rules"] = []

        def missing_rules(d):
            del d["test_cases"][0]["general_rules"]

        def b_fields(d):
            d["grader_visible_fields"] = ["question", "rubric", "student_answer"]

        def mixed(d):
            d["test_cases"][0]["group"] = "B"

        def unknown(d):
            for c in d["test_cases"]:
                c["group"] = "C"

        for change, message in [(add_policies, "also has grading_policies"), (empty_rules, "general_rules"),
                                (missing_rules, "general_rules"), (b_fields, "for Group A"),
                                (mixed, "expected one group"), (unknown, "unknown test-set group")]:
            with self.subTest(change.__name__), self.assertRaisesRegex(dataset.DatasetError, message):
                dataset.load(self.mutated(change), expected_sha256=None)

    def test_group_b_without_policies_refused(self):
        data = json.loads(dataset.DEFAULT_DATASET.read_text(encoding="utf-8"))
        del data["grading_policies"]
        with self.assertRaisesRegex(dataset.DatasetError, "grading_policies"):
            dataset.load(self.write(data), expected_sha256=None)

    def test_test_id_patterns(self):
        for tid in ("csc236_A_regex_04_a06", "csc236_A_asymptotic_analysis_03_a09"):
            self.assertTrue(dataset.TEST_ID_RE_A.match(tid), tid)
        for tid in ("csc236_B_regex_04_a06", "csc236_A_regex_4_a06", "csc236_A_regex_04_ans06", "csc236_A__04_a06"):
            self.assertFalse(dataset.TEST_ID_RE_A.match(tid), tid)
        self.assertFalse(dataset.TEST_ID_RE.match("csc236_A_regex_04_a06"))

        def rename(d):
            d["test_cases"][0]["test_id"] = "csc236_B_regex_04_ans06"

        ds = dataset.load(self.mutated(rename), expected_sha256=None)
        self.assertTrue(any("naming pattern" in p for p in dataset.check_structure(ds)))


class GroupAPromptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ds = dataset.load_group("A")
        cls.records = {r["test_id"]: r for r in prompt.build_prompts(cls.ds)}
        cls.b_policies = dataset.load().grading_policies

    def test_each_case_gets_its_own_rules(self):
        for case in self.ds.cases:
            with self.subTest(case["test_id"]):
                self.assertEqual(self.ds.general_rules(case), case["general_rules"])
                expected = prompt.build_messages(dataset.grader_input(case), case["general_rules"])
                self.assertEqual(self.records[case["test_id"]]["messages"], expected)
                text = user_text(expected)
                self.assertIn("General rules:\n1. ", text)
                for policy in self.b_policies:
                    self.assertNotIn(prompt.norm(policy)[:60], text)
        # Different seeds have different rules: 23 distinct rule lists over the 40 cases.
        self.assertEqual(prompt.describe(self.ds)["general_rules_distinct_sets"], 23)

    def test_context_is_the_training_seed_context(self):
        """Rendering question, rubric and the case's rules reproduces, byte for byte, the context of the
        training example the case came from (recorded as source.prompt_context_sha256)."""
        for case in self.ds.cases:
            with self.subTest(case["test_id"]):
                context = prompt.render_context({"question": case["question"], "criteria": case["rubric"],
                                                 "general_rules": case["general_rules"]})
                self.assertEqual(hashlib.sha256(context.encode("utf-8")).hexdigest(),
                                 case["source"]["prompt_context_sha256"])
                self.assertTrue(user_text(self.records[case["test_id"]]["messages"]).startswith(context))

    def test_student_answer_verbatim_and_last(self):
        for case in self.ds.cases:
            text = user_text(self.records[case["test_id"]]["messages"])
            self.assertTrue(text.endswith(prompt.ANSWER_LABEL + "\n" + case["student_answer"]))

    def test_no_held_out_text_in_prompts(self):
        """Labels, the generated reply, correction history, review notes and generation metadata never
        reach the prompt, unless the same text is part of what the model may see (e.g. an embedded
        instruction that is in the student answer)."""
        for case in self.ds.cases:
            text = "\n".join(m["content"] for m in self.records[case["test_id"]]["messages"])
            visible = "\n".join([case["question"], case["student_answer"], json.dumps(case["rubric"], ensure_ascii=False),
                                 *case["general_rules"]])
            with self.subTest(case["test_id"]):
                for field in ("test_id", "question_id", "seed_id"):
                    self.assertNotIn(case[field], text)
                self.assertNotIn(case["final_response_markdown"].strip(), text)
                self.assertNotIn(case["original_generated_label"]["raw_response"].strip(), text)
                held = prompt.held_out_strings(case)
                self.assertGreater(len(held), 5)
                for s in held:
                    if s not in visible:
                        self.assertNotIn(s, text)

    def test_leak_guard_covers_group_a_fields(self):
        case = next(c for c in self.ds.cases if c["corrections"])
        rules = case["general_rules"]
        messages = prompt.messages_for_case(self.ds, case)
        leaks = [case["final_response_markdown"], case["original_generated_label"]["raw_response"],
                 case["corrections"][0]["to"]["justification"], case["audit_notes"][0], case["selection_reason"],
                 case["generation_metadata"]["facts"], case["source"]["file"], case["seed_id"]]
        for leak in leaks:
            with self.subTest(leak[:40]):
                bad = [messages[0], {"role": "user", "content": messages[1]["content"] + "\n" + leak}]
                with self.assertRaises(prompt.LeakError):
                    prompt.check_no_leak(bad, case, rules)
        prompt.check_no_leak(messages, case, rules)

    def test_template_and_determinism(self):
        self.assertEqual(prompt.build_prompts(self.ds), prompt.build_prompts(self.ds))
        info = prompt.describe(self.ds)
        self.assertEqual(info["general_rules_source"], dataset.RULES_CASE)
        self.assertNotEqual(info["template_sha256"], GROUP_B_TEMPLATE_SHA256)
        self.assertEqual(info["template_sha256"], prompt.template_hash([], dataset.RULES_CASE))

    def test_labels_parse_with_the_unchanged_parser(self):
        """The stored gold reply and a reply rendered from the labels both parse back to the labels."""
        for case in self.ds.cases:
            gold = {g["criterion_id"]: (g["level"], g["score"]) for g in case["draft_ground_truth"]["criteria"]}
            for text in (case["final_response_markdown"], render_grade(case)):
                out = parse.parse_text(text, case["rubric"])
                with self.subTest(case["test_id"]):
                    self.assertEqual(out.case_status, "ok", out.issues)
                    self.assertEqual({c.criterion_id: (c.level, c.score) for c in out.criteria}, gold)
                    self.assertEqual(out.total, case["draft_ground_truth"]["total_score"])


@mock.patch.object(backends.VLLMBackend, "server_info", no_server_info)
class GroupARunTest(unittest.TestCase):
    """run_eval, rescore and compare on Group A with a fake client that grades with the labels."""

    @classmethod
    def setUpClass(cls):
        cls.ds = dataset.load_group("A")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_model(self, model, *args, out="runs", client=None):
        client = client or FakeServer(self.ds)
        code = quiet(run_eval.main, ["--model", model, "--out", str(self.tmp / out), "--endpoint",
                                     "http://fake:8000/v1", "--n-boot", "30", *args], client=client)
        runs = sorted((self.tmp / out).glob("*_*"))
        return code, (runs[-1] if runs else None), client

    def test_group_a_round_trip(self):
        code, run_dir, client = self.run_model("base", "--group", "A")
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 40)
        config = read_json(run_dir / "config.json")
        self.assertEqual(config["dataset"]["group"], "A")
        self.assertEqual(config["dataset"]["sha256"], dataset.GROUP_A_SHA256)
        self.assertEqual(config["prompt"]["general_rules_source"], dataset.RULES_CASE)
        self.assertIn("Group A labels", config["labels_note"])
        self.assertEqual(run_eval.read_jsonl(run_dir / "prompts.jsonl"), prompt.build_prompts(self.ds))
        m = read_json(run_dir / "metrics.json")
        self.assertIn("Group A labels", m["note"])
        self.assertIn("Group A labels", m["labels"]["note"])
        c = m["criterion"]
        self.assertEqual((c["strict_exact_agreement"]["value"], c["coverage"]["value"]), (1.0, 1.0))
        self.assertEqual(c["mae_points"], 0.0)
        self.assertEqual(m["qwk"]["levels"], 1.0)
        self.assertEqual(m["format"]["format_compliant_cases"]["value"], 1.0)
        self.assertEqual(m["total"]["strict_exact_total"]["value"], 1.0)
        summary = (run_dir / "summary.md").read_text(encoding="utf-8")
        self.assertIn("Group A labels (final v1)", summary)
        self.assertIn("Group A, final-v1-2026-11-16", summary)
        self.assertNotIn("Group B", summary)

        rescored = run_eval.rescore(run_dir)
        self.assertEqual(read_json(rescored / "metrics.json")["criterion"], c)

    def test_wrong_grades_are_scored_against_group_a_labels(self):
        case = self.ds.cases[0]
        wrong = [{**g, "level": "none", "score": 0} for g in case["draft_ground_truth"]["criteria"]]
        client = FakeServer(self.ds, replies={case["test_id"]: render_grade(case, wrong)})
        code, run_dir, _ = self.run_model("base", "--group", "A", "--question-id", case["question_id"], client=client)
        self.assertEqual(code, 0)
        rows = run_eval.read_jsonl(run_dir / "parsed.jsonl")
        self.assertEqual({r["test_id"] for r in rows}, {c["test_id"] for c in self.ds.cases
                                                       if c["question_id"] == case["question_id"]})
        m = read_json(run_dir / "metrics.json")
        self.assertLess(m["criterion"]["strict_exact_agreement"]["value"], 1.0)

    def test_dataset_options(self):
        load = run_eval.load_dataset
        self.assertEqual(load(None, None, None).group.name, "B")
        self.assertEqual(load("A", None, None).group.name, "A")
        self.assertEqual(load(None, str(dataset.GROUP_A_DATASET), None).group.name, "A")  # the group's file
        with self.assertRaisesRegex(dataset.DatasetError, "SHA-256"):
            load("A", str(dataset.DEFAULT_DATASET), dataset.GROUP_A_SHA256)
        with self.assertRaisesRegex(dataset.DatasetError, "not Group A"):
            load("A", str(dataset.DEFAULT_DATASET), None)
        with self.assertRaisesRegex(dataset.DatasetError, "not Group A"):
            load("A", str(dataset.DEFAULT_DATASET), dataset.EXPECTED_SHA256)
        code, run_dir, client = self.run_model("base", "--group", "A", "--dataset", str(dataset.DEFAULT_DATASET))
        self.assertEqual((code, run_dir, client.calls), (1, None, []))

    def test_compare_group_a_runs(self):
        _, base_dir, _ = self.run_model("base", "--group", "A", "--topic", "regex", out="base")
        _, ft_dir, _ = self.run_model("fine_tuned", "--group", "A", "--topic", "regex", out="ft")
        result = compare.compare(base_dir, ft_dir, n_boot=20)
        self.assertEqual(result["shared"]["dataset"]["group"], "A")
        self.assertIn("Group A labels", result["note"])
        self.assertIn("Group A labels (final v1)", compare.render(result))

    def test_runs_of_different_groups_not_compared(self):
        _, a_dir, _ = self.run_model("base", "--group", "A", "--question-id", self.ds.cases[0]["question_id"],
                                     out="a")
        b = dataset.load()
        _, b_dir, _ = self.run_model("fine_tuned", "--question-id", b.cases[0]["question_id"], out="b",
                                     client=FakeServer(b))
        with self.assertRaises(compare.CompareError):
            compare.compare(a_dir, b_dir, n_boot=10)


if __name__ == "__main__":
    unittest.main()
