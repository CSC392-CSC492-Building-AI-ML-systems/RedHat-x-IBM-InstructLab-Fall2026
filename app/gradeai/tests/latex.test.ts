import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { hasLatexMath, tokenizeLatex } from '../src/lib/latex'

describe('LaTeX submission extract tokenizer', () => {
  it('detects inline, display, and environment LaTeX math', () => {
    assert.strictEqual(hasLatexMath('plain text only'), false)
    assert.strictEqual(hasLatexMath('For all $n \\ge 1$, $P(n)$ holds.'), true)
    assert.strictEqual(hasLatexMath('$$\\sum_{i=1}^n i = \\frac{n(n+1)}{2}$$'), true)
    assert.strictEqual(hasLatexMath('\\[a^2 + b^2 = c^2\\]'), true)
    assert.strictEqual(hasLatexMath('\\begin{align*}x &= 1\\end{align*}'), true)
  })

  it('tokenizes prose, inline math, display math, page breaks, and [illegible] markers', () => {
    const sample = [
      '--- Page 1 ---',
      'Claim: For all $n \\ge 1$, we have \\(P(n)\\).',
      '$$\\sum_{i=1}^n i = \\frac{n(n+1)}{2}$$',
      'Step 2: [illegible] implies \\begin{align*}x &= 1 \\\\ y &= 2\\end{align*}',
      'Cost is \\$5.',
    ].join('\n')

    const tokens = tokenizeLatex(sample)
    assert.deepStrictEqual(tokens, [
      { type: 'page-break', value: 'Page 1' },
      { type: 'text', value: '\nClaim: For all ' },
      { type: 'inline-math', value: 'n \\ge 1' },
      { type: 'text', value: ', we have ' },
      { type: 'inline-math', value: 'P(n)' },
      { type: 'text', value: '.\n' },
      { type: 'display-math', value: '\\sum_{i=1}^n i = \\frac{n(n+1)}{2}' },
      { type: 'text', value: '\nStep 2: ' },
      { type: 'illegible', value: '[illegible]' },
      { type: 'text', value: ' implies ' },
      { type: 'display-math', value: '\\begin{align*}x &= 1 \\\\ y &= 2\\end{align*}' },
      { type: 'text', value: '\nCost is \\$5.' },
    ])
  })

  it('still tokenizes inline math inside non-math environments like itemize', () => {
    const sample = '\\begin{itemize}\n\\item Base case $n = 1$\n\\end{itemize}'
    const tokens = tokenizeLatex(sample)
    assert.ok(tokens.some(t => t.type === 'inline-math' && t.value === 'n = 1'))
  })
})
