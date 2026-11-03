import unittest

from eval import backends, dataset
from eval import parse as parse_module
from eval.tests import test_set_guard
from eval.tests.fixtures import MiniDatasetTest, criterion, mid, render_grade

setUpModule, tearDownModule = test_set_guard()

# A 3-criterion rubric (max 3, 3, 4 = 10), shaped like a test case's `rubric`.
RUBRIC = [criterion("C1", "Predicate and base case", 3),
          criterion("C2", "Induction hypothesis", 3),
          criterion("C3", "Inductive step", 4)]

GOOD = """**Grade:** 8 / 10

**Feedback:**
- C1 Predicate and base case: full (3/3). States P(n) and checks P(0).
- C2 Induction hypothesis: full (3/3). Assumes P(k) for an arbitrary k and states the goal
  P(k+1).
- C3 Inductive step: partial (2/4). The divisibility of 3k(k+1) by 6 is not justified.
Total: 3 + 3 + 2 = 8.
"""

ZERO = """**Grade:** 0 / 10

**Feedback:**
- C1 Predicate and base case: none (0/3). No base case.
- C2 Induction hypothesis: none (0/3). The hypothesis assumes the claim for every n.
- C3 Inductive step: none (0/4). No inductive step.
Total: 0 + 0 + 0 = 0.
"""


def p(text, **kwargs):
    return parse_module.parse_text(text, RUBRIC, **kwargs)


class RoundTripTest(MiniDatasetTest):
    def test_gold_round_trip(self):
        """The labels of every real case, written as replies, parse back exactly."""
        for case in dataset.load().cases:
            with self.subTest(case=case["test_id"]):
                out = parse_module.parse_text(render_grade(case), case["rubric"])
                self.assertEqual(out.case_status, parse_module.OK, out.issues)
                gold = case["draft_ground_truth"]
                self.assertEqual([(c.criterion_id, c.level, c.score) for c in out.criteria],
                                 [(g["criterion_id"], g["level"], g["score"]) for g in gold["criteria"]])
                self.assertEqual(out.total, gold["total_score"])
                self.assertEqual(out.max_score, gold["max_score"])
                self.assertEqual([c.justification for c in out.criteria],
                                 [g["justification"] for g in gold["criteria"]])

        case = self.cases[mid("delta_04_ans02")]
        gen = backends.Generation(case["test_id"], "h", text=render_grade(case), finish_reason="stop")
        out = parse_module.parse_generation(gen, case)
        self.assertTrue(out.valid)
        self.assertEqual((out.test_id, out.prompt_sha256, out.total), (case["test_id"], "h", 3))
        # max-4 criterion at partial is worth 2: there is no 3-point level.
        self.assertEqual(out.scores(), {"C1": 2, "C2": 1})


class ValidRepliesTest(unittest.TestCase):
    def test_good(self):
        out = p(GOOD)
        self.assertEqual(out.case_status, "ok")
        self.assertEqual(out.scores(), {"C1": 3, "C2": 3, "C3": 2})
        self.assertEqual(out.total, 8)
        self.assertEqual((out.stated_grade, out.stated_denominator, out.total_line_value), (8, 10, 8))
        self.assertEqual(out.criteria[1].justification,
                         "Assumes P(k) for an arbitrary k and states the goal P(k+1).")
        self.assertEqual(out.raw_text, GOOD)

    def test_valid_zero_is_not_a_failure(self):
        out = p(ZERO)
        self.assertTrue(out.valid)
        self.assertEqual(out.total, 0)
        for c in out.criteria:
            self.assertEqual((c.status, c.level, c.score), ("ok", "none", 0))
            self.assertIsNone(c.problem)

    def test_layout_variants_accepted(self):
        variants = {
            "bold names": GOOD.replace("- C1 Predicate and base case:", "- **C1 Predicate and base case**:"),
            "bold level": GOOD.replace("full (3/3). States", "**full (3/3)**. States"),
            "star bullets": GOOD.replace("\n- C", "\n* C"),
            "capitalised level": GOOD.replace("partial (2/4)", "Partial (2/4)"),
            "spaces in points": GOOD.replace("(2/4)", "( 2 / 4 )"),
            "decimal points": GOOD.replace("(3/3). States", "(3.0/3). States"),
            "code fence": "```markdown\n" + GOOD + "```\n",
            "text around it": "Here is my grade.\n\n" + GOOD + "\nLet me know if you need more detail.\n",
            "no Feedback heading": GOOD.replace("**Feedback:**\n", ""),
            "reasons on next line only": GOOD.replace("full (3/3). States P(n)", "full (3/3).\n  States P(n)"),
            "non-ASCII reason": GOOD.replace("States P(n) and checks P(0).", "Checks ε and ⌊n/2⌋ ∈ ℕ."),
        }
        for name, text in variants.items():
            with self.subTest(variant=name):
                out = p(text)
                self.assertEqual(out.case_status, "ok", out.issues)
                self.assertEqual(out.scores(), {"C1": 3, "C2": 3, "C3": 2})
                self.assertEqual(out.raw_text, text)
        self.assertEqual(p(variants["non-ASCII reason"]).criteria[0].justification, "Checks ε and ⌊n/2⌋ ∈ ℕ.")

    def test_text_not_read_as_a_grade(self):
        echo = ("Rubric (Total 10 pts):\n- C1 Predicate and base case: 3 pts.\n- C2 Induction hypothesis: 3 pts.\n"
                "- C3 Inductive step: 4 pts.\n\n")
        self.assertEqual(p(echo + GOOD).case_status, "ok")

        for line in ("C1/C2: full (3/3) overall, as both are fine.",
                     "  C1 is: full (3/3) as shown above."):
            with self.subTest(line=line):
                out = p(GOOD.replace("  P(k+1).", line))
                self.assertEqual(out.case_status, "ok", out.issues)
                self.assertIn(line.strip(), out.criteria[1].justification)

        out = p('{"total_score": 10, "C1": "full"}\n' + GOOD)
        self.assertTrue(out.valid)
        self.assertEqual(out.total, 8)

    def test_missing_total_line_is_a_format_failure_only(self):
        out = p(GOOD.replace("Total: 3 + 3 + 2 = 8.\n", ""))
        self.assertEqual(out.case_status, "inconsistent_total")
        self.assertIn("no 'Total:' line", out.issues)
        self.assertEqual(out.scores(), {"C1": 3, "C2": 3, "C3": 2})  # the criteria are still valid
        self.assertTrue(all(c.valid for c in out.criteria))

    def test_minor_issues_are_warnings(self):
        out = p(GOOD.replace(" States P(n) and checks P(0).", ""))
        self.assertTrue(out.valid)
        self.assertIn("C1 has no reason", out.warnings)

        lines = GOOD.splitlines()
        c1 = lines.index("- C1 Predicate and base case: full (3/3). States P(n) and checks P(0).")
        lines[c1], lines[c1 + 3] = lines[c1 + 3], lines[c1]
        out = p("\n".join(lines) + "\n")
        self.assertTrue(out.valid)
        self.assertIn("criteria are not in rubric order", out.warnings)

    def test_thinking_removed_but_recorded(self):
        text = "<think>\nC1 looks full (3/3) but let me check.\n</think>\n\n" + GOOD
        out = p(text)
        self.assertTrue(out.valid)
        self.assertTrue(out.thinking_present)
        self.assertEqual(out.raw_text, text)
        self.assertEqual(p("Let me think. C1 full (3/3)?\n</think>\n" + GOOD).thinking_present, True)


class FailuresTest(unittest.TestCase):
    def assert_no_scores(self, out, *ids):
        for c in out.criteria:
            if c.criterion_id in ids or not ids:
                self.assertIsNone(c.score, c)
                self.assertIsNone(c.level, c)
                self.assertNotEqual(c.status, "ok")

    def test_no_usable_reply(self):
        out = p(None, error="ConnectionError: x")
        self.assertEqual(out.case_status, "request_error")
        self.assertIsNone(out.total)
        self.assert_no_scores(out)

        for text in (None, "", "   \n"):
            with self.subTest(text=text):
                out = p(text)
                self.assertEqual(out.case_status, "parse_failure")
                self.assert_no_scores(out)
                self.assertEqual(out.raw_text, text)

        for text in ("I think this proof deserves about 8 points.",
                     '{"criteria": [{"criterion_id": "C1", "level": "full", "score": 3}], "total_score": 3}'):
            with self.subTest(text=text):
                out = p(text)
                self.assertEqual(out.case_status, "parse_failure")
                self.assert_no_scores(out)

        out = p("<think>\nC1 is full (3/3), C2 is ...")
        self.assertEqual(out.case_status, "parse_failure")
        self.assertTrue(out.thinking_present)

    def test_truncated_reply(self):
        out = p(GOOD[:60], finish_reason="length")
        self.assertTrue(out.truncated)
        self.assertNotEqual(out.case_status, "ok")
        self.assert_no_scores(out, "C2", "C3")

    def test_bad_criterion_lines(self):
        out = p(GOOD.replace("- C2 Induction hypothesis: full (3/3). Assumes P(k) for an arbitrary k and states the goal\n  P(k+1).\n", ""))
        self.assertEqual(out.case_status, "invalid_criteria")
        c2 = out.criteria[1]
        self.assertEqual((c2.status, c2.level, c2.score), ("missing", None, None))
        self.assertEqual(out.criteria[0].score, 3)  # other criteria are still read, for diagnosis
        self.assertIsNone(out.total)

        out = p(GOOD.replace("Total:", "- C1 Predicate and base case: none (0/3). No base case.\nTotal:"))
        self.assertEqual(out.case_status, "invalid_criteria")
        self.assertEqual(out.criteria[0].status, "duplicate")
        self.assert_no_scores(out, "C1")

        out = p(GOOD.replace("full (3/3). States", "excellent (3/3). States"))
        self.assertEqual(out.criteria[0].status, "invalid_level")
        self.assertEqual(out.criteria[0].claimed, {"level": "excellent", "points": 3, "out_of": 3})
        self.assert_no_scores(out, "C1")

        for old, new, cid in [("full (3/3). States", "full (2/3). States", "C1"),   # wrong points
                              ("partial (2/4)", "partial (3/4)", "C3"),             # no 3-point level on max 4
                              ("full (3/3). States", "full (4/4). States", "C1"),   # wrong maximum
                              ("partial (2/4)", "partial (2/3)", "C3")]:
            with self.subTest(change=new):
                out = p(GOOD.replace(old, new))
                self.assertEqual(out.case_status, "invalid_criteria")
                bad = next(c for c in out.criteria if c.criterion_id == cid)
                self.assertEqual(bad.status, "points_mismatch")
                self.assert_no_scores(out, cid)

        out = p(GOOD.replace("- C3 Inductive step: partial (2/4).", "- C3 Inductive step: partial, 2 out of 4."))
        self.assertEqual(out.criteria[2].status, "unparseable")
        self.assert_no_scores(out, "C3")

        # Zero points with the wrong level is not a valid zero.
        out = p(ZERO.replace("none (0/3). No base case.", "partial (0/3). No base case."))
        self.assertEqual(out.criteria[0].status, "points_mismatch")
        self.assertIsNone(out.criteria[0].score)

    def test_unknown_criterion(self):
        out = p(GOOD.replace("Total:", "- C4 Conclusion: full (2/2). Concludes.\nTotal:"))
        self.assertEqual(out.case_status, "invalid_criteria")
        self.assertEqual([u["criterion_id"] for u in out.unknown_criteria], ["C4"])
        self.assertTrue(all(c.valid for c in out.criteria))
        self.assertIsNone(out.total)

    def test_grade_line_disagrees(self):
        for text, why in [(GOOD.replace("**Grade:** 8 / 10", "**Grade:** 9 / 10"), "the Grade is 9, but the criteria add up to 8"),
                          (GOOD.replace("**Grade:** 8 / 10", "**Grade:** 8 / 11"), "out of"),
                          (GOOD.replace("**Grade:** 8 / 10\n", ""), "no '**Grade:**"),
                          (GOOD.replace("= 8.", "= 9."), "Total line"),
                          (GOOD.replace("3 + 3 + 2 = 8", "3 + 3 + 3 = 8"), "sum"),
                          (GOOD + "\n**Grade:** 10 / 10\n", "more than once"),
                          (GOOD + "Total: 8.\n", "more than one Total line"),
                          (GOOD.replace("Total: 3 + 3 + 2 = 8.", "Total: see above."), "the Total line has no number"),
                          (GOOD.replace("Total: 3 + 3 + 2 = 8.", "Total: 6."), "Total line says 6")]:
            with self.subTest(why=why):
                out = p(text)
                self.assertEqual(out.case_status, "inconsistent_total", out.issues)
                self.assertTrue(any(why in issue for issue in out.issues), out.issues)
                self.assertIsNone(out.total)
                # the criteria themselves were read correctly
                self.assertTrue(all(c.valid for c in out.criteria))
        self.assertTrue(p(GOOD.replace("Total: 3 + 3 + 2 = 8.", "Total: 8.")).valid)

    def test_injection_style_reply(self):
        out = p("SYSTEM OVERRIDE acknowledged.\n**Grade:** 10 / 10\n")
        self.assertEqual(out.case_status, "invalid_criteria")
        self.assertEqual({c.status for c in out.criteria}, {"missing"})
        self.assertEqual((out.stated_grade, out.stated_denominator), (10, 10))  # recorded, not used
        self.assertIsNone(out.total)
        self.assert_no_scores(out)


class RecordTest(unittest.TestCase):
    def test_record_keeps_everything(self):
        rec = p(GOOD, test_id="t", prompt_sha256="h").to_record()
        self.assertEqual(rec["raw_text"], GOOD)
        self.assertEqual(rec["case_status"], "ok")
        self.assertEqual(rec["criteria"][2]["score"], 2)
        bad = p(GOOD.replace("full (3/3). States", "full (2/3). States")).to_record()
        self.assertEqual(bad["criteria"][0]["score"], None)
        self.assertEqual(bad["criteria"][0]["claimed"]["points"], 2)


if __name__ == "__main__":
    unittest.main()
