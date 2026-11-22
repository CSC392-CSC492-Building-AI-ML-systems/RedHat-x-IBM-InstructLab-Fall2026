import { execFile, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { config } from './config'

/**
 * gemini-ocr.ts
 * Server-side OCR using the Gemini VLM API.
 * Used as the primary OCR path when GEMINI_API_KEY is set.
 * Falls back to Tesseract (ocr.ts) when it isn't.
 *
 * Uses Node 22 built-in `fetch` — no extra npm dependency required.
 */

const TRANSCRIPTION_PROMPT = `Transcribe this handwritten student proof exactly as written.
- Preserve mistakes and incorrect steps. Do NOT correct or complete anything.
- Write math in LaTeX (inline: $...$, display: $$...$$). Keep line breaks and numbering.
- Mark unreadable text as [illegible]. Never guess.
- For multi-page documents, separate each page with "--- Page X ---".
Output only the transcription.`

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

/** POST image or PDF data to the Gemini generateContent endpoint and return transcription text. */
async function callGemini(mimeType: string, base64Data: string): Promise<string> {
  const model = encodeURIComponent(config.geminiOcrModel)
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(config.geminiApiKey)}`
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

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const err = await res.text()
    throw new Error(`Gemini OCR API error ${res.status}: ${err.slice(0, 300)}`)
  }

  const data = (await res.json()) as {
    candidates?: { content?: { parts?: { text?: string }[] } }[]
  }
  return data.candidates?.[0]?.content?.parts?.map(p => p.text ?? '').join('') ?? ''
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
 *                 with pdftoppm fallback if direct upload fails and pdftoppm is installed.
 */
export async function geminiOcrFile(file: string, kind: 'scan' | 'image', maxPages = 12): Promise<string> {
  if (kind === 'image') {
    const base64Data = fs.readFileSync(file).toString('base64')
    return (await callGemini(imageMime(file), base64Data)).trim()
  }

  // kind === 'scan': Scanned PDF
  // Try sending the PDF directly first if under 20MB (fast, native Gemini PDF support, no external binaries required)
  const stats = fs.statSync(file)
  if (stats.size <= 20 * 1024 * 1024) {
    try {
      const base64Data = fs.readFileSync(file).toString('base64')
      const text = await callGemini('application/pdf', base64Data)
      if (text.trim()) return text.trim()
    } catch (err) {
      // If direct PDF is rejected, fall back to rasterizing pages if pdftoppm is available
      if (!hasPdftoppm()) throw err
    }
  }

  // Fallback: rasterize with pdftoppm and call Gemini per page
  if (!hasPdftoppm()) {
    throw new Error('pdftoppm (poppler-utils) is not installed and PDF direct upload failed.')
  }

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gradeai-gemini-ocr-'))
  try {
    const pages = await pdfPagesToPngs(file, maxPages, dir)
    if (!pages.length) throw new Error('No pages found in scanned PDF.')
    const results: string[] = []
    for (let i = 0; i < pages.length; i++) {
      const base64Data = fs.readFileSync(pages[i]).toString('base64')
      const text = await callGemini('image/png', base64Data)
      results.push(`--- Page ${i + 1} ---\n${text.trim()}`)
    }
    return results.join('\n\n')
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
}
