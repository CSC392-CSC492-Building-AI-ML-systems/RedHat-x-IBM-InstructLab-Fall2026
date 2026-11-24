import fs from 'node:fs'
import path from 'node:path'
import type { Response } from 'express'
import type { Submission } from '../src/lib/types'

const INLINE_MIME: Record<string, string> = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  webp: 'image/webp',
  gif: 'image/gif',
  svg: 'application/octet-stream', // never serve untrusted SVG as image/svg+xml inline
  txt: 'text/plain; charset=utf-8',
  md: 'text/plain; charset=utf-8',
  tex: 'text/plain; charset=utf-8',
  py: 'text/plain; charset=utf-8',
  java: 'text/plain; charset=utf-8',
  c: 'text/plain; charset=utf-8',
  h: 'text/plain; charset=utf-8',
  cpp: 'text/plain; charset=utf-8',
  hpp: 'text/plain; charset=utf-8',
  js: 'text/plain; charset=utf-8',
  ts: 'text/plain; charset=utf-8',
  json: 'text/plain; charset=utf-8',
  csv: 'text/plain; charset=utf-8',
}

/** Resolve the Content-Type header for inline viewing based on filename extension. */
export function inlineMimeType(filename: string): string {
  const idx = filename.lastIndexOf('.')
  const ext = idx >= 0 ? filename.slice(idx + 1).toLowerCase() : ''
  return INLINE_MIME[ext] ?? 'application/octet-stream'
}

/** Build a safe Content-Disposition header value for inline responses. */
export function inlineContentDisposition(filename: string): string {
  const base = path.basename(filename || 'file')
  const ascii = base.replace(/["\\\r\n]/g, '_').replace(/[^\x20-\x7E]/g, '_') || 'file'
  return `inline; filename="${ascii}"; filename*=UTF-8''${encodeURIComponent(base)}`
}

/** Resolve and validate that a submission's storedFile lives inside dataDir/files and exists on disk. */
export function resolveStoredFile(dataDir: string, storedFile: string): string | null {
  if (!storedFile) return null
  const filesRoot = path.resolve(dataDir, 'files')
  const abs = path.resolve(dataDir, storedFile)
  if (!abs.startsWith(filesRoot + path.sep) || !fs.existsSync(abs)) return null
  return abs
}

/** Send a stored submission file either as an inline preview or as a file download. */
export function sendStoredFile(res: Response, dataDir: string, sub: Pick<Submission, 'file' | 'storedFile'> | null, inline: boolean): void {
  if (!sub?.storedFile) {
    res.status(404).json({ error: 'not_found', message: 'The original file is not stored.' })
    return
  }
  const abs = resolveStoredFile(dataDir, sub.storedFile)
  if (!abs) {
    res.status(404).json({ error: 'not_found' })
    return
  }
  if (inline) {
    const name = sub.file || path.basename(abs)
    res.setHeader('Content-Type', inlineMimeType(name))
    res.setHeader('Content-Disposition', inlineContentDisposition(name))
    res.setHeader('Cache-Control', 'private, max-age=3600')
    res.sendFile(abs)
    return
  }
  res.download(abs, sub.file)
}
