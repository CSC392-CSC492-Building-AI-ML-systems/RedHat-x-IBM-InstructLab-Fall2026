import path from 'node:path'

function num(v: string | undefined, d: number) {
  const n = Number(v)
  return Number.isFinite(n) && n > 0 ? n : d
}

const publicUrl = (process.env.PUBLIC_URL || 'http://localhost:8080').replace(/\/$/, '')

export const config = {
  port: num(process.env.PORT, 8080),
  host: process.env.HOST || '0.0.0.0',
  dataDir: path.resolve(process.env.DATA_DIR || './data'),
  publicUrl,
  /** Shared secret the Fir worker sends as "Authorization: Bearer <token>". */
  workerToken: process.env.WORKER_TOKEN || '',
  cookieSecure: process.env.COOKIE_SECURE ? process.env.COOKIE_SECURE === 'true' : publicUrl.startsWith('https://'),
  trustProxy: process.env.TRUST_PROXY ? process.env.TRUST_PROXY === 'true' : true,
  maxUploadMb: num(process.env.MAX_UPLOAD_MB, 25),
  sessionDays: num(process.env.SESSION_DAYS, 14),
  /** A worker is considered online if it checked in within this many seconds. */
  workerTimeoutSec: num(process.env.WORKER_TIMEOUT_SEC, 90),
  /** How long a claimed task may run before it returns to the queue. */
  leaseSec: num(process.env.TASK_LEASE_SEC, 600),
  maxAttempts: num(process.env.TASK_MAX_ATTEMPTS, 3),
  staticDir: path.resolve(process.env.STATIC_DIR || './dist'),
  /** Gemini API key for VLM-based OCR. When set, Gemini is used instead of Tesseract. */
  geminiApiKey: process.env.GEMINI_API_KEY || '',
  /** Gemini model to use for OCR. Defaults to gemini-2.0-flash. */
  geminiOcrModel: process.env.GEMINI_OCR_MODEL || 'gemini-2.0-flash',
}

export const STAFF = new Set(['professor', 'admin'])
