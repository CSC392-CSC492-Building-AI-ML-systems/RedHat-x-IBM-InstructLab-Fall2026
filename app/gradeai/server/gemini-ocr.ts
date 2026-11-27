import { execFile, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { config } from './config'

/**
 * gemini-ocr.ts
 * Server-side OCR using the Gemini VLM API.
 * Used as the primary OCR path when GEMINI_API_KEY is set.
 * Tesseract (ocr.ts) is used only when no Gemini key is set; there is no fallback between them.
 */

const TRANSCRIPTION_PROMPT = `Transcribe this handwritten student proof exactly as written.
- Preserve mistakes and incorrect steps. Do NOT correct or complete anything.
- Write math in LaTeX (inline: $...$, display: $$...$$). Keep line breaks and numbering.
- Mark unreadable text as [illegible]. Never guess.
- For multi-page documents, separate each page with "--- Page X ---".
Output only the transcription.`

const BLOCKED_REASONS = new Set(['SAFETY', 'RECITATION', 'PROHIBITED_CONTENT', 'SPII', 'BLOCKLIST'])
const RETRYABLE_STATUS = new Set([429, 500, 502, 503, 504])
/** Direct-PDF failures that page-by-page rasterization can plausibly fix. */
const PDF_RASTERIZE_ON = new Set<GeminiOcrErrorCode>(['bad_request', 'truncated'])

export type GeminiOcrErrorCode =
  | 'timeout'
  | 'network'
  | 'rate_limit'
  | 'auth'
  | 'not_found'
  | 'bad_request'
  | 'blocked'
  | 'truncated'
  | 'server'
  | 'invalid_response'

export class GeminiOcrError extends Error {
  readonly code: GeminiOcrErrorCode
  readonly retryable: boolean
  readonly status?: number
  /** Server-requested delay from a Retry-After header, if any. */
  readonly retryAfterMs: number | null

  constructor(
    message: string,
    opts: { code: GeminiOcrErrorCode; retryable: boolean; status?: number; retryAfterMs?: number | null },
  ) {
    super(message)
    this.name = 'GeminiOcrError'
    this.code = opts.code
    this.retryable = opts.retryable
    this.status = opts.status
    this.retryAfterMs = opts.retryAfterMs ?? null
  }
}

export interface GeminiCallOptions {
  timeoutMs?: number
  maxRetries?: number
  /** Base exponential backoff delay in ms (kept configurable for tests). */
  baseBackoffMs?: number
}

function hasPdftoppm() {
  try { return spawnSync('pdftoppm', ['-v'], { stdio: 'ignore', timeout: 5000 }).status === 0 } catch { return false }
}

function run(cmd: string, args: string[], timeout = 120_000): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { timeout, maxBuffer: 32 * 1024 * 1024 }, (err, stdout) => (err ? reject(err) : resolve(String(stdout))))
  })
}

/** Rasterize a PDF to PNGs in a temp dir. Returns sorted list of PNG paths. */
async function pdfPagesToPngs(pdfPath: string, maxPages: number, dir: string): Promise<string[]> {
  await run('pdftoppm', ['-r', '200', '-png', '-l', String(maxPages), pdfPath, path.join(dir, 'p')])
  return fs.readdirSync(dir).filter(f => f.endsWith('.png')).sort().map(f => path.join(dir, f))
}

function scrubSecrets(text: string): string {
  let out = text.replace(/([?&]key=)[^&\s]+/gi, '$1[REDACTED]')
  if (config.geminiApiKey) out = out.split(config.geminiApiKey).join('[REDACTED]')
  return out
}

function parseErrorDetail(raw: string): string {
  const trimmed = raw.trim()
  if (!trimmed) return 'Empty error response'
  try {
    const parsed = JSON.parse(trimmed) as { error?: { message?: string; status?: string } }
    if (parsed?.error?.message) {
      const prefix = parsed.error.status ? `${parsed.error.status}: ` : ''
      return scrubSecrets(`${prefix}${parsed.error.message}`).slice(0, 300)
    }
  } catch { /* plain text body */ }
  return scrubSecrets(trimmed).slice(0, 300)
}

function parseRetryAfterMs(headerVal: string | null): number | null {
  if (!headerVal) return null
  const secs = Number(headerVal)
  if (Number.isFinite(secs) && secs >= 0) return Math.min(60_000, Math.round(secs * 1000))
  const at = Date.parse(headerVal)
  if (Number.isFinite(at)) return Math.max(0, Math.min(60_000, at - Date.now()))
  return null
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/** Gemini reports a bad API key as HTTP 400 with reason API_KEY_INVALID, not 401/403. */
const AUTH_DETAIL_RE = /API_KEY_INVALID|API key not valid|API_KEY_SERVICE_BLOCKED|UNAUTHENTICATED|PERMISSION_DENIED/i

function classifyHttpError(status: number, detail: string, retryAfterMs: number | null = null): GeminiOcrError {
  if (status === 429) {
    return new GeminiOcrError(`Gemini OCR rate limit (HTTP 429): ${detail}`, { code: 'rate_limit', retryable: true, status, retryAfterMs })
  }
  if (status === 401 || status === 403 || (status === 400 && AUTH_DETAIL_RE.test(detail))) {
    return new GeminiOcrError(`Gemini OCR authentication error (${status}): ${detail}`, { code: 'auth', retryable: false, status })
  }
  if (status === 404) {
    return new GeminiOcrError(
      `Gemini OCR model "${config.geminiOcrModel}" not found (HTTP 404): ${detail}`,
      { code: 'not_found', retryable: false, status },
    )
  }
  if (RETRYABLE_STATUS.has(status)) {
    return new GeminiOcrError(`Gemini OCR API error ${status}: ${detail}`, { code: 'server', retryable: true, status, retryAfterMs })
  }
  return new GeminiOcrError(`Gemini OCR API error ${status}: ${detail}`, { code: 'bad_request', retryable: false, status })
}

function isAbortError(err: unknown): boolean {
  return err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError')
}

/** Perform a single Gemini generateContent call. The timeout covers both the request and reading the body. */
async function callGeminiOnce(mimeType: string, base64Data: string, timeoutMs: number): Promise<string> {
  // A plain timer (not AbortSignal.timeout, whose timer is unref'd) so the call is bounded even if
  // nothing else is holding the event loop open.
  const ac = new AbortController()
  const timer = setTimeout(() => ac.abort(new DOMException('Timed out', 'TimeoutError')), timeoutMs)
  try {
    return await callGeminiWithSignal(mimeType, base64Data, timeoutMs, ac.signal)
  } finally {
    clearTimeout(timer)
  }
}

async function callGeminiWithSignal(mimeType: string, base64Data: string, timeoutMs: number, signal: AbortSignal): Promise<string> {
  const model = encodeURIComponent(config.geminiOcrModel)
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`
  const body = {
    contents: [
      {
        parts: [
          { text: TRANSCRIPTION_PROMPT },
          { inlineData: { mimeType, data: base64Data } },
        ],
      },
    ],
    generationConfig: {
      temperature: 0,
    },
  }

  const started = Date.now()
  const timeoutError = () => {
    console.error(`[OCR] Gemini API timeout (${config.geminiOcrModel}) after ${Date.now() - started}ms`)
    return new GeminiOcrError(`Gemini OCR timed out after ${Math.round(timeoutMs / 1000)}s.`, { code: 'timeout', retryable: true })
  }

  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-goog-api-key': config.geminiApiKey,
      },
      body: JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (isAbortError(err)) throw timeoutError()
    const msg = scrubSecrets(err instanceof Error ? err.message : String(err))
    console.error(`[OCR] Gemini API request failed (${config.geminiOcrModel}) after ${Date.now() - started}ms: ${msg}`)
    throw new GeminiOcrError(`Gemini OCR network error: ${msg}`, { code: 'network', retryable: true })
  }

  if (!res.ok) {
    let rawErr = ''
    try { rawErr = await res.text() } catch (err) { if (isAbortError(err)) throw timeoutError() }
    const detail = parseErrorDetail(rawErr)
    const retryAfterMs = parseRetryAfterMs(res.headers?.get?.('retry-after') ?? null)
    console.error(`[OCR] Gemini API error (${config.geminiOcrModel}) HTTP ${res.status} in ${Date.now() - started}ms: ${detail.slice(0, 200)}`)
    throw classifyHttpError(res.status, detail, retryAfterMs)
  }

  let data: {
    candidates?: { finishReason?: string; content?: { parts?: { text?: string }[] } }[]
    promptFeedback?: { blockReason?: string }
  }
  try {
    data = (await res.json()) as typeof data
  } catch (err) {
    if (isAbortError(err)) throw timeoutError()
    console.error(`[OCR] Gemini API invalid JSON (${config.geminiOcrModel}) HTTP ${res.status} in ${Date.now() - started}ms`)
    throw new GeminiOcrError('Gemini OCR returned an unreadable response.', { code: 'invalid_response', retryable: true, status: res.status })
  }
  const elapsed = Date.now() - started

  if (data.promptFeedback?.blockReason) {
    console.error(`[OCR] Gemini API blocked (${config.geminiOcrModel}) HTTP ${res.status} in ${elapsed}ms: ${data.promptFeedback.blockReason}`)
    throw new GeminiOcrError(`Gemini OCR blocked the submission (${data.promptFeedback.blockReason}).`, { code: 'blocked', retryable: false, status: res.status })
  }

  const candidate = data.candidates?.[0]
  if (!candidate) {
    console.error(`[OCR] Gemini API empty candidates (${config.geminiOcrModel}) HTTP ${res.status} in ${elapsed}ms`)
    throw new GeminiOcrError('Gemini OCR returned no transcription candidates.', { code: 'invalid_response', retryable: true, status: res.status })
  }

  const finishReason = candidate.finishReason
  const text = candidate.content?.parts?.map(p => p.text ?? '').join('') ?? ''

  if (finishReason && BLOCKED_REASONS.has(finishReason)) {
    console.error(`[OCR] Gemini API stopped (${config.geminiOcrModel}) HTTP ${res.status} in ${elapsed}ms: finish=${finishReason}`)
    throw new GeminiOcrError(`Gemini OCR stopped (${finishReason}).`, { code: 'blocked', retryable: false, status: res.status })
  }

  if (finishReason === 'MAX_TOKENS') {
    console.warn(`[OCR] Gemini API truncated (${config.geminiOcrModel}) HTTP ${res.status} in ${elapsed}ms (${text.length} chars, finish=MAX_TOKENS)`)
    throw new GeminiOcrError('Gemini OCR output exceeded token limit (MAX_TOKENS).', { code: 'truncated', retryable: false, status: res.status })
  }

  console.log(
    `[OCR] Gemini API ok (${config.geminiOcrModel}) HTTP ${res.status} in ${elapsed}ms (${text.length} chars${finishReason ? `, finish=${finishReason}` : ''})`,
  )
  return text
}

/** POST image or PDF data to Gemini generateContent with timeout and exponential-backoff retries. */
async function callGemini(mimeType: string, base64Data: string, opts: GeminiCallOptions = {}): Promise<string> {
  const timeoutMs = opts.timeoutMs ?? config.geminiOcrTimeoutMs
  const maxRetries = opts.maxRetries ?? config.geminiOcrMaxRetries
  const baseBackoffMs = opts.baseBackoffMs ?? 1000

  let lastErr: unknown
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await callGeminiOnce(mimeType, base64Data, timeoutMs)
    } catch (err) {
      lastErr = err
      if (!(err instanceof GeminiOcrError) || !err.retryable || attempt >= maxRetries) throw err

      const headerDelay = err.retryAfterMs
      const jitter = Math.round(Math.random() * Math.min(250, baseBackoffMs * 0.25))
      const backoff = headerDelay ?? Math.min(15_000, baseBackoffMs * 2 ** attempt + jitter)
      console.warn(`[OCR] Retrying Gemini (${attempt + 1}/${maxRetries}) in ${backoff}ms: ${err.message}`)
      if (backoff > 0) await sleep(backoff)
    }
  }
  throw lastErr
}

/** MIME type lookup for common image extensions. */
function imageMime(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase().slice(1)
  const map: Record<string, string> = {
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    webp: 'image/webp',
    gif: 'image/gif',
  }
  return map[ext] ?? 'image/jpeg'
}

/**
 * OCR a scanned PDF or image file using the Gemini VLM.
 * - Images:       sent directly as base64.
 * - Scanned PDFs: sent directly as application/pdf (supported natively by Gemini),
 *                 with pdftoppm page-by-page fallback if direct upload fails and pdftoppm is installed.
 */
export async function geminiOcrFile(
  file: string,
  kind: 'scan' | 'image',
  maxPages = 12,
  opts: GeminiCallOptions = {},
): Promise<string> {
  if (kind === 'image') {
    const base64Data = fs.readFileSync(file).toString('base64')
    return (await callGemini(imageMime(file), base64Data, opts)).trim()
  }

  // kind === 'scan': Scanned PDF
  // Try sending the PDF directly first if under 20MB (fast, native Gemini PDF support, no external binaries required)
  const stats = fs.statSync(file)
  if (stats.size <= 20 * 1024 * 1024) {
    try {
      const base64Data = fs.readFileSync(file).toString('base64')
      const text = await callGemini('application/pdf', base64Data, opts)
      if (text.trim()) return text.trim()
    } catch (err) {
      // Only rasterize when Gemini rejected or truncated this particular PDF. Transient failures
      // (timeouts, 429, 5xx) already exhausted their retries, and page-by-page calls would just
      // repeat them once per page; config errors (auth, not_found) would fail every page too.
      const pdfSpecific = err instanceof GeminiOcrError && PDF_RASTERIZE_ON.has(err.code)
      if (!pdfSpecific || !hasPdftoppm()) throw err
      console.warn(`[OCR] Direct PDF upload failed (${err.code}); rasterizing pages with pdftoppm`)
    }
  }

  // Fallback: rasterize with pdftoppm and call Gemini per page
  if (!hasPdftoppm()) {
    throw new Error('pdftoppm (poppler-utils) is not installed and PDF direct upload failed or exceeded 20 MB.')
  }

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gradeai-gemini-ocr-'))
  try {
    const pages = await pdfPagesToPngs(file, maxPages, dir)
    if (!pages.length) throw new Error('No pages found in scanned PDF.')
    const results: string[] = []
    for (let i = 0; i < pages.length; i++) {
      const base64Data = fs.readFileSync(pages[i]).toString('base64')
      const text = await callGemini('image/png', base64Data, opts)
      results.push(`--- Page ${i + 1} ---\n${text.trim()}`)
    }
    return results.join('\n\n')
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
}
