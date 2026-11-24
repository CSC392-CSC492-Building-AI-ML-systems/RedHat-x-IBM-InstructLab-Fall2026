export type LatexToken =
  | { type: 'text'; value: string }
  | { type: 'inline-math'; value: string }
  | { type: 'display-math'; value: string }
  | { type: 'page-break'; value: string }
  | { type: 'illegible'; value: string }

const MATH_ENV_PATTERN = [
  'equation\\*?',
  'align\\*?',
  'aligned',
  'gather\\*?',
  'gathered',
  'multline\\*?',
  'cases',
  'dcases',
  'split',
  'matrix',
  'pmatrix',
  'bmatrix',
  'Bmatrix',
  'vmatrix',
  'Vmatrix',
  'array',
].join('|')

const TOKEN_RE = new RegExp(
  [
    // Page divider lines emitted by OCR / PDF reader
    '(^---\\s*Page\\s+\\d+\\s*---$)',
    // Display math: $$...$$
    '(\\$\\$[\\s\\S]+?\\$\\$)',
    // Display math: \[...\]
    '(\\\\\\[[\\s\\S]+?\\\\\\])',
    // Standalone LaTeX math environments: \begin{env}...\end{env}
    `(\\\\begin\\{(${MATH_ENV_PATTERN})\\}[\\s\\S]+?\\\\end\\{\\5\\})`,
    // Inline math: \(...\)
    '(\\\\\\([^\\n]+?\\\\\\))',
    // Inline math: $...$ (single line, non-empty, not starting/ending with $$ and respecting \$)
    '(?<![\\\\$])\\$(?!\\$)((?:\\\\.|[^$\\\\\\n])+?)(?<![\\\\])\\$(?!\\$)',
    // [illegible] marker from OCR prompt
    '(\\[illegible\\])',
  ].join('|'),
  'gm',
)

/** Quick check for whether a text extract appears to contain LaTeX math. */
export function hasLatexMath(input: string): boolean {
  if (!input) return false
  return /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([^\n]+?\\\)|(?<![\\$])\$(?!\$)(?:\\.|[^$\\\n])+?\$(?!\$)|\\begin\{(?:equation|align|gather|cases|bmatrix|pmatrix)/.test(input)
}

/** Tokenize OCR / submission text into plain text, inline/display LaTeX math, page breaks, and [illegible] markers. */
export function tokenizeLatex(input: string): LatexToken[] {
  if (!input) return []
  const tokens: LatexToken[] = []
  let lastIndex = 0
  TOKEN_RE.lastIndex = 0

  for (const match of input.matchAll(TOKEN_RE)) {
    const idx = match.index ?? 0
    const full = match[0]
    const [
      ,
      pageBreak,
      doubleDollar,
      bracketDisplay,
      envBlock,
      ,
      parenInline,
      singleDollarInner,
      illegible,
    ] = match

    if (idx > lastIndex) {
      tokens.push({ type: 'text', value: input.slice(lastIndex, idx) })
    }

    if (pageBreak) {
      tokens.push({ type: 'page-break', value: pageBreak.replace(/^-+\s*|\s*-+$/g, '') })
    } else if (doubleDollar) {
      tokens.push({ type: 'display-math', value: doubleDollar.slice(2, -2).trim() })
    } else if (bracketDisplay) {
      tokens.push({ type: 'display-math', value: bracketDisplay.slice(2, -2).trim() })
    } else if (envBlock) {
      tokens.push({ type: 'display-math', value: envBlock.trim() })
    } else if (parenInline) {
      tokens.push({ type: 'inline-math', value: parenInline.slice(2, -2).trim() })
    } else if (singleDollarInner !== undefined) {
      tokens.push({ type: 'inline-math', value: singleDollarInner.trim() })
    } else if (illegible) {
      tokens.push({ type: 'illegible', value: illegible })
    } else {
      tokens.push({ type: 'text', value: full })
    }

    lastIndex = idx + full.length
  }

  if (lastIndex < input.length) {
    tokens.push({ type: 'text', value: input.slice(lastIndex) })
  }

  return tokens
}
