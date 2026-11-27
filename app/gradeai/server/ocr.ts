import { execFile, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

/* Reads scanned PDFs and photos on this server with Tesseract, so student work never leaves your infrastructure. */

function has(cmd: string, arg = '--version') {
  try { return spawnSync(cmd, [arg], { stdio: 'ignore', timeout: 5000 }).status === 0 } catch { return false }
}

export const ocrTools = { tesseract: has('tesseract'), pdftoppm: has('pdftoppm', '-v') }

function run(cmd: string, args: string[], timeout = 120_000): Promise<string> {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { timeout, maxBuffer: 32 * 1024 * 1024 }, (err, stdout) => (err ? reject(err) : resolve(String(stdout))))
  })
}

export async function ocrFile(file: string, kind: 'scan' | 'image', maxPages = 12): Promise<string> {
  if (!ocrTools.tesseract) throw new Error('Tesseract is not installed on the server, so scanned work cannot be read. Install tesseract-ocr (and poppler-utils for PDFs).')
  if (kind === 'image') return (await run('tesseract', [file, 'stdout', '-l', 'eng'])).trim()
  if (!ocrTools.pdftoppm) throw new Error('pdftoppm (poppler-utils) is not installed on the server, so scanned PDFs cannot be read.')
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gradeai-ocr-'))
  try {
    await run('pdftoppm', ['-r', '200', '-png', '-l', String(maxPages), file, path.join(dir, 'p')])
    const pages = fs.readdirSync(dir).filter(f => f.endsWith('.png')).sort()
    const out: string[] = []
    for (let i = 0; i < pages.length; i++) {
      const t = await run('tesseract', [path.join(dir, pages[i]), 'stdout', '-l', 'eng'])
      out.push(`--- Page ${i + 1} ---\n${t.trim()}`)
    }
    return out.join('\n\n')
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
}

import { geminiOcrFile, type GeminiCallOptions } from './gemini-ocr'
import { config } from './config'

/**
 * Primary OCR entry point.
 * Uses Gemini when GEMINI_API_KEY is set, otherwise Tesseract. There is deliberately no
 * Gemini -> Tesseract fallback: Tesseract garbles handwriting, and a failed OCR with a clear
 * error is better than silently grading unreadable text.
 */
export async function ocrFileAuto(
  file: string,
  kind: 'scan' | 'image',
  maxPages = 12,
  opts: GeminiCallOptions = {},
): Promise<string> {
  if (config.geminiApiKey) {
    console.log(`[OCR] Using Gemini (${config.geminiOcrModel}) for ${path.basename(file)}`)
    return geminiOcrFile(file, kind, maxPages, opts)
  }
  console.log(`[OCR] Using Tesseract for ${path.basename(file)}`)
  return ocrFile(file, kind, maxPages)
}

/** Which OCR backend is currently active (reported to the UI via /api/me). */
export const ocrBackend: 'gemini' | 'tesseract' | 'none' =
  config.geminiApiKey ? 'gemini' : ocrTools.tesseract ? 'tesseract' : 'none'

