import { describe, it, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import type { Response } from 'express'
import {
  inlineContentDisposition,
  inlineMimeType,
  resolveStoredFile,
  sendStoredFile,
} from '../server/file-serving'

function makeMockRes() {
  const headers: Record<string, string> = {}
  const calls: { status?: number; json?: unknown; download?: [string, string]; sendFile?: string } = {}
  const res = {
    status(code: number) {
      calls.status = code
      return this
    },
    json(body: unknown) {
      calls.json = body
      return this
    },
    setHeader(name: string, val: string) {
      headers[name.toLowerCase()] = val
      return this
    },
    download(abs: string, filename: string) {
      calls.download = [abs, filename]
      return this
    },
    sendFile(abs: string) {
      calls.sendFile = abs
      return this
    },
  }
  return { res: res as unknown as Response, headers, calls }
}

describe('File serving helpers (inline & download)', () => {
  let tmpDir: string

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'gradeai-files-'))
    fs.mkdirSync(path.join(tmpDir, 'files', 's123'), { recursive: true })
  })

  afterEach(() => {
    if (fs.existsSync(tmpDir)) fs.rmSync(tmpDir, { recursive: true, force: true })
  })

  it('maps image, PDF, text, and unsafe extensions to safe MIME types', () => {
    assert.strictEqual(inlineMimeType('scan.pdf'), 'application/pdf')
    assert.strictEqual(inlineMimeType('PHOTO.JPG'), 'image/jpeg')
    assert.strictEqual(inlineMimeType('proof.jpeg'), 'image/jpeg')
    assert.strictEqual(inlineMimeType('work.png'), 'image/png')
    assert.strictEqual(inlineMimeType('page.webp'), 'image/webp')
    assert.strictEqual(inlineMimeType('anim.gif'), 'image/gif')
    assert.strictEqual(inlineMimeType('solution.py'), 'text/plain; charset=utf-8')
    assert.strictEqual(inlineMimeType('diagram.svg'), 'application/octet-stream')
    assert.strictEqual(inlineMimeType('unknown.bin'), 'application/octet-stream')
  })

  it('builds sanitized inline Content-Disposition headers', () => {
    const disp = inlineContentDisposition('hw2 "proof"\n.pdf')
    assert.ok(disp.startsWith('inline; filename="hw2 _proof__.pdf"; filename*=UTF-8\'\''))
  })

  it('prevents path traversal outside dataDir/files', () => {
    const outside = path.join(tmpDir, 'secret.txt')
    fs.writeFileSync(outside, 'secret')
    assert.strictEqual(resolveStoredFile(tmpDir, '../secret.txt'), null)
    assert.strictEqual(resolveStoredFile(tmpDir, 'secret.txt'), null)

    const valid = path.join(tmpDir, 'files', 's123', 'proof.pdf')
    fs.writeFileSync(valid, '%PDF-1.4')
    assert.strictEqual(resolveStoredFile(tmpDir, path.join('files', 's123', 'proof.pdf')), valid)
  })

  it('serves attachment by default and inline with MIME headers when inline=true', () => {
    const rel = path.join('files', 's123', 'proof.pdf')
    const abs = path.join(tmpDir, rel)
    fs.writeFileSync(abs, '%PDF-1.4')

    const dl = makeMockRes()
    sendStoredFile(dl.res, tmpDir, { file: 'proof.pdf', storedFile: rel }, false)
    assert.deepStrictEqual(dl.calls.download, [abs, 'proof.pdf'])
    assert.strictEqual(dl.calls.sendFile, undefined)

    const inl = makeMockRes()
    sendStoredFile(inl.res, tmpDir, { file: 'proof.pdf', storedFile: rel }, true)
    assert.strictEqual(inl.calls.sendFile, abs)
    assert.strictEqual(inl.headers['content-type'], 'application/pdf')
    assert.ok(inl.headers['content-disposition'].startsWith('inline;'))
  })

  it('returns 404 when storedFile is missing or non-existent', () => {
    const missing = makeMockRes()
    sendStoredFile(missing.res, tmpDir, { file: 'proof.pdf', storedFile: '' }, true)
    assert.strictEqual(missing.calls.status, 404)

    const gone = makeMockRes()
    sendStoredFile(gone.res, tmpDir, { file: 'proof.pdf', storedFile: 'files/s123/nope.pdf' }, true)
    assert.strictEqual(gone.calls.status, 404)
  })
})
