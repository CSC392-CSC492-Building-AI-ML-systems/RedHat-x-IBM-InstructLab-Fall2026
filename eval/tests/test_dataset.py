import copy
import tempfile
import unittest
from pathlib import Path

from eval import dataset
from eval.tests import test_set_guard
from eval.tests.fixtures import MINI_SIZE, MiniDatasetTest, mid, mini_data, write_mini

setUpModule, tearDownModule = test_set_guard()


class LoadTest(MiniDatasetTest):
    def test_hash_is_enforced(self):
        real = dataset.load()
        self.assertEqual(real.sha256, dataset.EXPECTED_SHA256)
        self.assertGreater(len(real.cases), 0)
        with self.assertRaisesRegex(dataset.DatasetError, "expected"):
            dataset.load(expected_sha256="0" * 64)
        info = self.ds.describe()
        self.assertEqual((info["version"], info["case_count"], info["sha256"]),
                         ("fixture-v1", MINI_SIZE["cases"], self.ds.sha256))
        self.assertIn("FIXTURE", info["status"])
        self.assertEqual(len(self.ds.grading_policies), 4)
        with tempfile.TemporaryDirectory() as tmp:
            # Another version under the expected file name is still refused.
            path = write_mini(tmp, name=dataset.DEFAULT_DATASET.name)
            with self.assertRaises(dataset.DatasetError):
                dataset.load(path)
            # Inspecting another version has to be asked for explicitly.
            self.assertEqual(len(dataset.load(path, expected_sha256=None).cases), MINI_SIZE["cases"])

    def test_change_during_run_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_mini(tmp)
            ds = dataset.load(path, expected_sha256=dataset.sha256_file(path))
            dataset.verify_unchanged(ds)
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(dataset.DatasetError, "changed"):
                dataset.verify_unchanged(ds)

    def test_unsupported_visible_fields_rejected(self):
        data = mini_data()
        data["grader_visible_fields"] = ["question", "rubric", "student_answer", "ta_score"]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(dataset.DatasetError, "grader_visible_fields"):
                dataset.load(write_mini(tmp, data), expected_sha256=None)


class StructureTest(MiniDatasetTest):
    def problems(self, change):
        data = copy.deepcopy(self.ds.data)
        change(data, {c["test_id"]: c for c in data["test_cases"]})
        return dataset.check_structure(dataset.Dataset(self.ds.path, self.ds.sha256, data))

    def test_real_dataset_has_no_structure_problems(self):
        self.assertEqual(dataset.check_structure(dataset.load()), [])

    def test_structure_problems_reported(self):
        q, para, sens = mid("alpha_01_ans01"), mid("alpha_01_ans01_para1"), mid("alpha_01_ans01_sens1")
        other = mid("alpha_01_ans02")

        def rubric(fn):
            return lambda d, c: fn(c[q]["rubric"])

        def set_(key, value, tid=q):
            return lambda d, c: c[tid].__setitem__(key, value)

        def set_label(tid, level, score):
            def change(d, c):
                g = c[tid]["draft_ground_truth"]["criteria"][0]
                g["level"], g["score"] = level, score
            return change

        cases = {
            "full is not worth 2 points": set_label(q, "full", 2),
            "total_score": set_label(q, "full", 2),
            "although the relation is identical_to_parent": set_label(para, "partial", 2),
            "criteria_changes": lambda d, c: c[sens]["expected_relation_to_parent"].__setitem__("criteria_changes", {"C2": -2}),
            "ta_criteria": lambda d, c: c[other]["ta_criteria"].__setitem__("C1", 99),
            "appears twice in the rubric": rubric(lambda r: r[1].__setitem__("id", "C1")),
            "levels are": rubric(lambda r: r[0]["levels"].pop("minimal")),
            "full is": rubric(lambda r: r[0].__setitem__("max", 4)),
            "none is": rubric(lambda r: r[0]["levels"]["none"].__setitem__("points", 1)),
            "do not strictly decrease": rubric(lambda r: r[0]["levels"]["minimal"].__setitem__("points", 2)),
            "does not end with [N marks]": set_("question", "Prove it."),
            "marks] but the rubric": lambda d, c: c[q].__setitem__("question", c[q]["question"].replace("[10 marks]", "[12 marks]")),
            "do not match the rubric": lambda d, c: c[other]["draft_ground_truth"]["criteria"].pop(),
            "is not a rubric level": lambda d, c: c[q]["draft_ground_truth"]["criteria"][0].__setitem__("level", "great"),
            "max_score does not equal": lambda d, c: c[q]["draft_ground_truth"].__setitem__("max_score", 99),
            "ta_score does not equal": set_("ta_score", 1),
            "an original should have no parent": set_("parent_test_id", other),
            "is not in the dataset": set_("parent_test_id", mid("nope_99_ans01"), para),
            "parent has a different question_id": set_("parent_test_id", mid("beta_02_ans01"), para),
            "expected identical_to_parent": lambda d, c: c[para].__setitem__(
                "expected_relation_to_parent", {"relation": "lower_than_parent"}),
            "expected lower_than_parent": lambda d, c: c[sens].__setitem__(
                "expected_relation_to_parent", {"relation": "identical_to_parent"}),
            "total_change does not equal": lambda d, c: c[sens]["expected_relation_to_parent"].__setitem__("total_change", -5),
            "case_count is": lambda d, c: d.__setitem__("case_count", 99),
            "test_id appears more than once": lambda d, c: d["test_cases"].append(copy.deepcopy(c[q])),
            "fields missing": lambda d, c: c[q].pop("subtopic"),
            "naming pattern": set_("test_id", mid("alpha_01_answer1")),
            "unknown test_type": set_("test_type", "adversarial", other),
            "expected exactly one original": lambda d, c: c[para].__setitem__("test_type", "original"),
        }
        self.assertEqual(self.problems(lambda d, c: None), [])
        for fragment, change in cases.items():
            with self.subTest(problem=fragment):
                found = self.problems(change)
                self.assertTrue(any(fragment in p for p in found), found)

    def test_grader_input_is_only_visible_fields(self):
        for case in dataset.load().cases + self.ds.cases:
            self.assertEqual(list(dataset.grader_input(case)), ["question", "rubric", "student_answer"])


class SelectionTest(MiniDatasetTest):
    def test_filters_select_matching_cases(self):
        s = dataset.select(self.ds)
        self.assertEqual(len(s.selected_ids), MINI_SIZE["cases"])
        self.assertEqual(s.context_parent_ids, [])

        s = dataset.select(self.ds, question_ids=[mid("alpha_01")])
        self.assertEqual(len(s.selected_ids), 6)
        self.assertEqual(s.context_parent_ids, [])

        s = dataset.select(self.ds, test_types=["sensitivity"], topics=["induction_a"])
        self.assertEqual(s.selected_ids, [mid("alpha_01_ans01_sens1")])
        self.assertEqual(s.context_parent_ids, [mid("alpha_01_ans01")])
        self.assertEqual(s.role(mid("alpha_01_ans01")), dataset.CONTEXT_PARENT)
        self.assertIsNone(s.role(mid("beta_02_ans01")))

        s = dataset.select(self.ds, topics=["automata_c"])
        self.assertEqual(len(s.selected_ids), 8)
        self.assertEqual(s.context_parent_ids, [])

        order = [c["test_id"] for c in self.ds.cases]
        ids = [i.test_id for i in dataset.select(self.ds, test_types=["robustness"]).items]
        self.assertEqual(ids, sorted(ids, key=order.index))

    def test_variant_filter_adds_parents_as_context_only(self):
        s = dataset.select(self.ds, test_types=["paraphrase"])
        self.assertEqual(len(s.selected_ids), 3)
        self.assertEqual(s.context_parent_ids, [mid("alpha_01_ans01"), mid("delta_04_ans01")])
        self.assertTrue(all(c["test_type"] == "paraphrase" for c in s.selected))
        self.assertEqual(s.headline(), "3 selected (+2 context parents run for reference)")
        info = s.describe()
        self.assertEqual((info["selected_count"], info["context_parent_count"]), (3, 2))

        # A parent that is selected itself is listed once, and not as context.
        s = dataset.select(self.ds, test_types=["paraphrase", "original"])
        self.assertEqual(len(s.selected_ids), 3 + 8)
        self.assertEqual(s.context_parent_ids, [])
        ids = [i.test_id for i in s.items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_unknown_filter_value_rejected(self):
        for kwargs in ({"test_types": ["paraphrases"]}, {"topics": ["no_such_topic"]},
                       {"question_ids": [mid("nope_99")]}):
            with self.assertRaises(dataset.DatasetError):
                dataset.select(self.ds, **kwargs)


if __name__ == "__main__":
    unittest.main()
