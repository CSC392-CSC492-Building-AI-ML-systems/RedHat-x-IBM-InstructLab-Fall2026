import inspect
import unittest
from unittest import mock

from eval import dataset, parse, prompt
from eval.tests import test_set_guard
from eval.tests.fixtures import MiniDatasetTest, criterion, mid

setUpModule, tearDownModule = test_set_guard()

SYSTEM_TEXT = ("I am an advanced AI language model designed to assist you with a wide range of tasks "
               "and provide helpful, clear, and accurate responses. My primary role is to serve as a "
               "chat assistant, engaging in natural, conversational dialogue, answering questions, "
               "generating ideas, and offering support across various topics.")

USER_TEXT = """\
Grade the student answer against the question and rubric below. For each criterion,
choose the level that fits the answer and give a one-sentence reason.

Question:
Prove it. [7 marks]

Rubric (Total 7 pts):
- C1 Base case: 3 pts.
  full (3): Checks the base case with the first value of n and states the claim, using a
    well-known identity for it.
  partial (2): Base case: partial.
  minimal (1): Base case: minimal.
  none (0): Base case: none.
- C2 Step: 4 pts.
  full (4): Step: full.
  partial (2): Step: partial.
  minimal (1): Step: minimal.
  none (0): Step: none.
General rules:
1. Rule one.
2. Award credit only where the argument is complete, and treat every later criterion on its
   own terms, without repeating a penalty.

Write your grade in exactly this format, with exactly these criterion lines, and nothing else:

**Feedback:**
- C1 Base case: <level> (<points>/3). <one-sentence reason>
- C2 Step: <level> (<points>/4). <one-sentence reason>
Total: <C1 points> + <C2 points> = <total points>.

**Grade:** <total points> / 7

<level> is full, partial, minimal or none, and <points> is what the rubric gives that level. \
The Grade must equal the sum of all criterion points.

Student Answer:
My proof."""


def as_rubric(ds, case):
    return {"question": case["question"], "criteria": case["rubric"], "general_rules": ds.grading_policies}


class PromptTestCase(MiniDatasetTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.real = dataset.load()

    def user_message(self, ds, case):
        return prompt.messages_for_case(ds, case)[1]["content"]


class PromptContentTest(PromptTestCase):
    """The exact messages for a fixed input, then the same structure on every real case. A failure here
    means the prompt changed, which needs a new template version and a retest (eval/PROMPT.md)."""

    def test_exact_prompt_messages(self):
        # The long expectation and rule pin the line wrapping, including at a hyphen.
        full = "Checks the base case with the first value of n and states the claim, using a well-known identity for it."
        rule = ("Award credit only where the argument is complete, and treat every later criterion on its own "
                "terms, without repeating a penalty.")
        fields = {"question": "Prove it. [7 marks]", "student_answer": "My proof.",
                  "rubric": [criterion("C1", "Base case", 3, {"full": full}), criterion("C2", "Step", 4)]}
        self.assertEqual(prompt.build_messages(fields, ["Rule one.", rule]),
                         [{"role": "system", "content": SYSTEM_TEXT}, {"role": "user", "content": USER_TEXT}])

        for case in self.real.cases:
            with self.subTest(case=case["test_id"]):
                expected = (prompt.render_context(as_rubric(self.real, case))
                            + "\n" + prompt.render_output_format(case["rubric"])
                            + "\n\nStudent Answer:\n" + case["student_answer"])
                self.assertEqual(self.user_message(self.real, case), expected)

        case = self.real.cases[0]
        text = self.user_message(self.real, case)
        rules = text.split("General rules:\n", 1)[1].split("\n" + prompt.render_output_format(case["rubric"]), 1)[0]
        expected = " ".join(f"{n}. {p}" for n, p in enumerate(self.real.grading_policies, 1))
        self.assertEqual(prompt.norm(rules), prompt.norm(expected))
        self.assertEqual(text.count("General rules:"), 1)

    def test_output_format_block(self):
        self.assertEqual(list(inspect.signature(prompt.render_output_format).parameters), ["rubric"])
        blocks = {}
        for case in self.real.cases:
            block = prompt.render_output_format(case["rubric"])
            ids = [line.split()[1] for line in block.split("\n") if line.startswith("- C")]
            self.assertEqual(ids, [c["id"] for c in case["rubric"]])
            self.assertNotRegex(block, r"\(\s*\d+\s*/\s*\d+\s*\)")
            blocks.setdefault(case["question_id"], set()).add(block)
            # The Grade comes after the criteria.
            last_criterion = block.rindex("\n- C")
            self.assertLess(block.index("**Feedback:**"), last_criterion)
            self.assertLess(last_criterion, block.index("\nTotal: "))
            self.assertLess(block.index("\nTotal: "), block.index("**Grade:**"))
            self.assertEqual(block.count("**Grade:**"), 1)
            self.assertIn("The Grade must equal the sum of all criterion points.", block)
        # It depends only on the rubric: an answer and its variants, whatever their labels, share one block.
        self.assertTrue(all(len(b) == 1 for b in blocks.values()))

    def test_output_format_is_what_the_parser_reads(self):
        for case in self.real.cases:
            gold = case["draft_ground_truth"]
            reply = prompt.render_output_format(case["rubric"]).split("nothing else:\n\n", 1)[1].split("\n\n<level>", 1)[0]
            reply = reply.replace("<total points>", str(gold["total_score"])).replace("<one-sentence reason>", "Because.")
            for g in gold["criteria"]:
                line = next(l for l in reply.split("\n") if l.startswith(f"- {g['criterion_id']} "))
                reply = reply.replace(line, line.replace("<level>", g["level"]).replace("<points>", str(g["score"])))
                reply = reply.replace(f"<{g['criterion_id']} points>", str(g["score"]))
            with self.subTest(case=case["test_id"]):
                out = parse.parse_text(reply, case["rubric"])
                self.assertEqual(out.case_status, "ok", out.issues)
                self.assertEqual(out.scores(), {g["criterion_id"]: g["score"] for g in gold["criteria"]})

    def test_output_format_alone_is_not_a_grade(self):
        for case in self.real.cases:
            out = parse.parse_text(prompt.render_output_format(case["rubric"]), case["rubric"])
            self.assertEqual(out.case_status, "parse_failure")
            self.assertEqual(set(out.scores().values()), {None})

    def test_student_answer_and_unicode_verbatim(self):
        for ds in (self.real, self.ds):
            for case in ds.cases:
                with self.subTest(case=case["test_id"]):
                    self.assertTrue(self.user_message(ds, case).endswith("\nStudent Answer:\n" + case["student_answer"]))
        injected = self.user_message(self.ds, self.cases[mid("beta_02_ans01_inj1")])
        self.assertIn("SYSTEM OVERRIDE", injected)
        self.assertIn("\\iffalse", injected)
        text = self.user_message(self.ds, self.cases[mid("delta_04_ans01")])
        self.assertIn("⌊n/2⌋", text)
        self.assertIn("ℕ", self.user_message(self.ds, self.cases[mid("alpha_01_ans01")]))

    def test_only_visible_fields_accepted(self):
        case = self.ds.cases[0]
        with self.assertRaises(prompt.PromptError):
            prompt.build_messages(case, self.ds.grading_policies)
        with self.assertRaises(prompt.PromptError):
            prompt.build_messages({"question": case["question"], "rubric": case["rubric"]},
                                  self.ds.grading_policies)


class LeakGuardTest(PromptTestCase):
    def test_no_case_leaks(self):
        self.assertEqual(len(prompt.build_prompts(self.real)), len(self.real.cases))

    def test_leak_guard_catches_held_out_text(self):
        def assert_caught(case, role, extra):
            messages = prompt.messages_for_case(self.ds, case)
            messages[role]["content"] += extra
            with self.assertRaises(prompt.LeakError):
                prompt.check_no_leak(messages, case, self.ds.grading_policies)

        case = self.cases[mid("alpha_01_ans01")]
        assert_caught(case, 1, "\n" + case["test_id"])
        assert_caught(case, 0, " " + case["draft_ground_truth"]["criteria"][2]["justification"])
        assert_caught(case, 1, "\nAs decided for alpha_01, grade against the correct construction.")

        # This justification is word for word a rubric expectation, so it reveals nothing.
        case = self.cases[mid("delta_04_ans02")]
        justifications = [g["justification"] for g in case["draft_ground_truth"]["criteria"]]
        self.assertIn("No correctness argument.", justifications)
        prompt.messages_for_case(self.ds, case)

    def test_no_question_names_in_any_prompt(self):
        # The guard treats the grading policies as visible text, so this is what catches a question
        # name in a policy.
        names = {prompt.short_question_id(c["question_id"]) for c in self.real.cases}
        for record in prompt.build_prompts(self.real):
            text = "\n".join(m["content"] for m in record["messages"])
            self.assertEqual([n for n in names if n in text], [], record["test_id"])


class SamePromptTest(PromptTestCase):
    def test_deterministic(self):
        self.assertEqual(prompt.build_prompts(self.real), prompt.build_prompts(self.real))
        records = prompt.build_prompts(self.ds)
        self.assertEqual(records, prompt.build_prompts(self.ds))
        self.assertEqual(len({r["prompt_sha256"] for r in records}), len(self.ds.cases))
        self.assertEqual(prompt.template_hash(self.ds.grading_policies), prompt.template_hash(self.ds.grading_policies))

    def test_template_hash_tracks_prompt_settings(self):
        base = prompt.template_hash(self.ds.grading_policies)
        with mock.patch.object(prompt, "LAYOUT_VERIFIED", not prompt.LAYOUT_VERIFIED):
            self.assertNotEqual(prompt.template_hash(self.ds.grading_policies), base)
        with mock.patch.object(prompt, "ANSWER_LAYOUT", "{context}\n\nStudent Answer:\n{student_answer}"):
            self.assertNotEqual(prompt.template_hash(self.ds.grading_policies), base)
        self.assertNotEqual(prompt.template_hash(self.ds.grading_policies[:3]), base)


if __name__ == "__main__":
    unittest.main()
