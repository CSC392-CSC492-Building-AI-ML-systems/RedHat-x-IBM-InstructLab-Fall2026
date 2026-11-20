/**
 * Verification test suite for GradeAI's Dual Response Normalizer.
 * Tests parsing of both JSON and InstructLab Markdown outputs.
 *
 * Run with: node --import tsx scripts/test-parser.ts
 * or bundle/run via tsx or node with loader.
 */

import assert from 'node:assert'
import { parseAndNormalizeGradeReply, parseMarkdownGrade, parseJsonLoose } from '../src/lib/grading.js'
import type { Rubric } from '../src/lib/types.js'

const testRubric: Rubric = {
  id: 'r1',
  name: 'A2 — Induction Proofs',
  assignment: 'Assignment 2',
  version: 'v1.0',
  createdBy: 'Prof. Mahmoud',
  updatedAt: Date.now(),
  totalPoints: 40,
  criteria: [
    {
      name: 'Base Case',
      points: 10,
      description: 'Identifies and proves base case.',
      levels: [
        { label: 'Full', points: 10, description: 'Base case proven.' },
        { label: 'Partial', points: 6, description: 'Base case has gaps.' },
        { label: 'None', points: 0, description: 'No base case.' },
      ],
    },
    {
      name: 'Inductive Hypothesis',
      points: 10,
      description: 'States IH for arbitrary k.',
      levels: [
        { label: 'Full', points: 10, description: 'IH stated correctly.' },
        { label: 'Partial', points: 6, description: 'IH weakly stated.' },
        { label: 'None', points: 0, description: 'Missing IH.' },
      ],
    },
    {
      name: 'Inductive Step',
      points: 15,
      description: 'Proves k+1 assuming k.',
      levels: [
        { label: 'Full', points: 15, description: 'Logically complete.' },
        { label: 'Partial', points: 9, description: 'Algebra error.' },
        { label: 'None', points: 0, description: 'No step.' },
      ],
    },
    {
      name: 'Conclusion',
      points: 5,
      description: 'Final wrapping statement.',
      levels: [
        { label: 'Full', points: 5, description: 'Explicit conclusion.' },
        { label: 'Partial', points: 3, description: 'Vague conclusion.' },
        { label: 'None', points: 0, description: 'No conclusion.' },
      ],
    },
  ],
}

console.log('--- Testing Dual Response Normalizer ---')

// 1. Test Standard JSON Input
console.log('Test 1: JSON response (e.g. from mock-model or vLLM json_schema)')
const jsonInput = JSON.stringify({
  student_name: 'John Doe',
  student_id: '1009876543',
  criteria: [
    { name: 'Base Case', level: 'Full', earned: 10, max: 10, note: 'Base case is verified correctly.' },
    { name: 'Inductive Hypothesis', level: 'Full', earned: 10, max: 10, note: 'IH stated precisely.' },
    { name: 'Inductive Step', level: 'Partial', earned: 9, max: 15, note: 'Minor algebra slip.' },
    { name: 'Conclusion', level: 'Full', earned: 5, max: 5, note: 'Clear conclusion.' },
  ],
  summary: 'Strong proof overall with minor algebra issue in inductive step.',
  confidence: 92,
  concerns: [],
})

const res1 = parseAndNormalizeGradeReply(jsonInput, testRubric)
assert.strictEqual(res1.score, 34)
assert.strictEqual(res1.studentName, 'John Doe')
assert.strictEqual(res1.criteria.length, 4)
assert.strictEqual(res1.criteria[2].earned, 9)
assert.strictEqual(res1.confidence, 92)
console.log('✓ Test 1 passed (JSON)')

// 2. Test InstructLab / grade_first Markdown Format
console.log('Test 2: Standard InstructLab / grade_first Markdown format')
const mdInput = `**Grade:** 34 / 40

**Feedback:**
- C1 Base Case: full (10/10). Base case is verified correctly.
- C2 Inductive Hypothesis: full (10/10). IH stated precisely and references arbitrary k.
- C3 Inductive Step: partial (9/15). Minor algebra slip on line 4 when expanding the sum.
- C4 Conclusion: full (5/5). Explicit conclusion referencing the original claim.
Total: 10 + 10 + 9 + 5 = 34.`

const res2 = parseAndNormalizeGradeReply(mdInput, testRubric)
assert.strictEqual(res2.score, 34)
assert.strictEqual(res2.criteria.length, 4)
assert.strictEqual(res2.criteria[0].level, 'Full')
assert.strictEqual(res2.criteria[0].earned, 10)
assert.strictEqual(res2.criteria[2].level, 'Partial')
assert.strictEqual(res2.criteria[2].earned, 9)
assert.strictEqual(res2.criteria[2].note, 'Minor algebra slip on line 4 when expanding the sum.')
assert.strictEqual(res2.concerns.length, 0)
console.log('✓ Test 2 passed (InstructLab Markdown)')

// 3. Test Markdown with Thinking Tokens (<think>...</think>)
console.log('Test 3: Markdown with reasoning model thinking tokens')
const thinkingInput = `<think>
Let me read the student's base case. They check n=0: 4^0 - 1 = 0, which is divisible by 3. That is full marks.
For the inductive hypothesis, they assume it holds for k.
The inductive step has a small calculation mistake.
</think>
**Feedback:**
- C1 Base Case: full (10/10). Base case is verified for n=0.
- C2 Inductive Hypothesis: full (10/10). Correctly stated.
- C3 Inductive Step: partial (9/15). Small calculation error.
- C4 Conclusion: full (5/5). Clear wrapping statement.

Total: 10 + 10 + 9 + 5 = 34.
**Grade:** 34 / 40`

const res3 = parseAndNormalizeGradeReply(thinkingInput, testRubric)
assert.strictEqual(res3.score, 34)
assert.strictEqual(res3.criteria[0].earned, 10)
assert.strictEqual(res3.criteria[2].earned, 9)
console.log('✓ Test 3 passed (Thinking token stripping + eval-v3 layout)')

// 4. Test Markdown without C1/C2 Labels (Fuzzy Name Matching)
console.log('Test 4: Markdown matching by criterion names without C-labels')
const nameOnlyInput = `**Feedback:**
- Base Case: full (10/10). Very good base case.
- Inductive Hypothesis: partial (6/10). Forgot to state that k is arbitrary.
- Inductive Step: full (15/15). Complete and rigorous proof.
- Conclusion: partial (3/5). Slightly vague summary.

**Grade:** 34 / 40`

const res4 = parseAndNormalizeGradeReply(nameOnlyInput, testRubric)
assert.strictEqual(res4.score, 34)
assert.strictEqual(res4.criteria[1].earned, 6)
assert.strictEqual(res4.criteria[1].level, 'Partial')
assert.strictEqual(res4.criteria[3].earned, 3)
console.log('✓ Test 4 passed (Fuzzy Name Matching)')

// 5. Test Arithmetic Discrepancy Detection (Flagging for Review)
console.log('Test 5: Arithmetic discrepancy detection generates concerns')
const badMathInput = `**Grade:** 30 / 40

**Feedback:**
- C1 Base Case: full (10/10). Good.
- C2 Inductive Hypothesis: full (10/10). Good.
- C3 Inductive Step: full (15/15). Good.
- C4 Conclusion: full (5/5). Good.
Total: 10 + 10 + 15 + 5 = 40.`

const res5 = parseAndNormalizeGradeReply(badMathInput, testRubric)
assert.strictEqual(res5.score, 40)
assert.ok(res5.concerns.some(c => c.includes('stated grade (30) disagrees with criterion sum (40)')))
assert.ok(res5.confidence < 80) // lowered confidence to trigger review
console.log('✓ Test 5 passed (Discrepancy detection & confidence lowering)')

console.log('\nAll 5 Dual Response Normalizer tests passed successfully!')
