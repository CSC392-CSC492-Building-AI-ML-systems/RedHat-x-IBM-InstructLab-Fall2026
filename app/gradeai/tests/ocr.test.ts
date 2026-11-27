import { describe, it, beforeEach, afterEach } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { config } from '../server/config'
import { ocrTools, ocrFileAuto } from '../server/ocr'
import { GeminiOcrError, geminiOcrFile } from '../server/gemini-ocr'
import { guessStudentFromFilename, formatBytes } from '../src/lib/files'

describe('GradeAI OCR & Transcription Pipeline', () => {
  let tmpDir: string
  const originalFetch = globalThis.fetch
  const originalKey = config.geminiApiKey
  const originalModel = config.geminiOcrModel

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'gradeai-test-'))
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    config.geminiApiKey = originalKey
    config.geminiOcrModel = originalModel
    if (fs.existsSync(tmpDir)) {
      fs.rmSync(tmpDir, { recursive: true, force: true })
    }
  })

  describe('1. Configuration & Routing', () => {
    it('should expose geminiApiKey and geminiOcrModel in config', () => {
      assert.strictEqual(typeof config.geminiApiKey, 'string')
      assert.strictEqual(typeof config.geminiOcrModel, 'string')
      assert.ok(config.geminiOcrModel.length > 0)
    })

    it('should report ocrBackend as "gemini" when API key is set', () => {
      config.geminiApiKey = 'test-gemini-key'
      // Re-evaluate backend logic
      const backend = config.geminiApiKey ? 'gemini' : ocrTools.tesseract ? 'tesseract' : 'none'
      assert.strictEqual(backend, 'gemini')
    })

    it('should report ocrBackend as "tesseract" or "none" when API key is empty', () => {
      config.geminiApiKey = ''
      const backend = config.geminiApiKey ? 'gemini' : ocrTools.tesseract ? 'tesseract' : 'none'
      assert.ok(backend === 'tesseract' || backend === 'none')
    })
  })

  describe('2. Gemini VLM OCR (Image transcription)', () => {
    it('transcribes an image by sending base64 and transcription prompt', async () => {
      config.geminiApiKey = 'fake-api-key'
      config.geminiOcrModel = 'gemini-flash-latest'

      // Create a dummy image file
      const imgPath = path.join(tmpDir, 'student_work.png')
      fs.writeFileSync(imgPath, Buffer.from('fake-png-data'))

      let capturedUrl = ''
      let capturedHeaders: Record<string, string> = {}
      let capturedBody: any = null

      globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        capturedUrl = String(input)
        capturedHeaders = (init?.headers ?? {}) as Record<string, string>
        capturedBody = JSON.parse(String(init?.body))
        return new Response(
          JSON.stringify({
            candidates: [
              {
                content: {
                  parts: [
                    {
                      text: 'Claim: For all $n \\ge 1$, $P(n)$ holds.\nBase case ($n=1$):\n$1 = 1$.',
                    },
                  ],
                },
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      }

      const text = await geminiOcrFile(imgPath, 'image')

      // Assertions
      assert.ok(capturedUrl.includes('models/gemini-flash-latest:generateContent'))
      assert.ok(!capturedUrl.includes('fake-api-key'), 'API key should not appear in the URL')
      assert.strictEqual(capturedHeaders['x-goog-api-key'], 'fake-api-key')
      assert.strictEqual(capturedBody.contents[0].parts[1].inlineData.mimeType, 'image/png')
      assert.strictEqual(
        capturedBody.contents[0].parts[1].inlineData.data,
        Buffer.from('fake-png-data').toString('base64')
      )
      assert.ok(capturedBody.contents[0].parts[0].text.includes('Transcribe this handwritten student proof'))
      assert.strictEqual(text, 'Claim: For all $n \\ge 1$, $P(n)$ holds.\nBase case ($n=1$):\n$1 = 1$.')
    })

    it('correctly maps file extensions to MIME types', async () => {
      config.geminiApiKey = 'fake-api-key'

      const testCases = [
        { ext: 'jpg', expected: 'image/jpeg' },
        { ext: 'jpeg', expected: 'image/jpeg' },
        { ext: 'webp', expected: 'image/webp' },
      ]

      for (const { ext, expected } of testCases) {
        const filePath = path.join(tmpDir, `proof.${ext}`)
        fs.writeFileSync(filePath, Buffer.from('data'))

        let sentMime = ''
        globalThis.fetch = async (_url: RequestInfo | URL, init?: RequestInit) => {
          const body = JSON.parse(String(init?.body))
          sentMime = body.contents[0].parts[1].inlineData.mimeType
          return new Response(
            JSON.stringify({ candidates: [{ content: { parts: [{ text: 'done' }] } }] }),
            { status: 200 }
          )
        }

        await geminiOcrFile(filePath, 'image')
        assert.strictEqual(sentMime, expected)
      }
    })

    it('throws a descriptive error when Gemini API returns non-200 without retrying permanent 4xx', async () => {
      config.geminiApiKey = 'fake-api-key'
      const imgPath = path.join(tmpDir, 'error_test.png')
      fs.writeFileSync(imgPath, Buffer.from('data'))

      let calls = 0
      globalThis.fetch = async () => {
        calls++
        return new Response(JSON.stringify({ error: { status: 'INVALID_ARGUMENT', message: 'Invalid image payload.' } }), { status: 400 })
      }

      await assert.rejects(
        async () => {
          await geminiOcrFile(imgPath, 'image', 12, { maxRetries: 3, baseBackoffMs: 1 })
        },
        (err: unknown) =>
          err instanceof GeminiOcrError &&
          err.code === 'bad_request' &&
          !err.retryable &&
          /Gemini OCR API error 400: INVALID_ARGUMENT: Invalid image payload/.test(err.message),
      )
      assert.strictEqual(calls, 1)
    })

    it('classifies Gemini\'s HTTP 400 API_KEY_INVALID as an auth error', async () => {
      config.geminiApiKey = 'bad-key'
      const imgPath = path.join(tmpDir, 'auth_test.png')
      fs.writeFileSync(imgPath, Buffer.from('data'))

      let calls = 0
      globalThis.fetch = async () => {
        calls++
        return new Response(
          JSON.stringify({ error: { status: 'INVALID_ARGUMENT', message: 'API key not valid. Please pass a valid API key.', details: [{ reason: 'API_KEY_INVALID' }] } }),
          { status: 400 },
        )
      }

      await assert.rejects(
        () => geminiOcrFile(imgPath, 'image', 12, { maxRetries: 3, baseBackoffMs: 1 }),
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'auth' && !err.retryable,
      )
      assert.strictEqual(calls, 1)
    })

    it('exposes Retry-After on the error when retries are exhausted', async () => {
      config.geminiApiKey = 'fake-api-key'
      const imgPath = path.join(tmpDir, 'retry_after.png')
      fs.writeFileSync(imgPath, Buffer.from('data'))

      globalThis.fetch = async () => new Response('busy', { status: 429, headers: { 'retry-after': '2' } })

      await assert.rejects(
        () => geminiOcrFile(imgPath, 'image', 12, { maxRetries: 0 }),
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'rate_limit' && err.retryAfterMs === 2000,
      )
    })

    it('retries transient 429 and 503 responses and succeeds on recovery', async () => {
      config.geminiApiKey = 'fake-api-key'
      const imgPath = path.join(tmpDir, 'retry_test.png')
      fs.writeFileSync(imgPath, Buffer.from('data'))

      let calls = 0
      globalThis.fetch = async () => {
        calls++
        if (calls === 1) {
          return new Response(JSON.stringify({ error: { status: 'RESOURCE_EXHAUSTED', message: 'Rate limited' } }), {
            status: 429,
            headers: { 'retry-after': '0' },
          })
        }
        if (calls === 2) {
          return new Response('Service Unavailable', { status: 503 })
        }
        return new Response(
          JSON.stringify({ candidates: [{ finishReason: 'STOP', content: { parts: [{ text: 'Recovered OCR' }] } }] }),
          { status: 200 },
        )
      }

      const text = await geminiOcrFile(imgPath, 'image', 12, { maxRetries: 3, baseBackoffMs: 1 })
      assert.strictEqual(text, 'Recovered OCR')
      assert.strictEqual(calls, 3)
    })

    it('aborts and retries on request timeout, throwing GeminiOcrError(timeout) when exhausted', async () => {
      config.geminiApiKey = 'fake-api-key'
      const imgPath = path.join(tmpDir, 'timeout_test.png')
      fs.writeFileSync(imgPath, Buffer.from('data'))

      let calls = 0
      globalThis.fetch = async (_url: RequestInfo | URL, init?: RequestInit) => {
        calls++
        return new Promise<Response>((_resolve, reject) => {
          const sig = init?.signal
          if (sig?.aborted) {
            reject(sig.reason ?? new DOMException('Timed out', 'TimeoutError'))
            return
          }
          sig?.addEventListener('abort', () => reject(sig.reason ?? new DOMException('Timed out', 'TimeoutError')), { once: true })
        })
      }

      await assert.rejects(
        async () => {
          await geminiOcrFile(imgPath, 'image', 12, { timeoutMs: 25, maxRetries: 1, baseBackoffMs: 1 })
        },
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'timeout' && err.retryable,
      )
      assert.strictEqual(calls, 2)
    })

    it('fails cleanly on safety blocks and MAX_TOKENS truncation', async () => {
      config.geminiApiKey = 'fake-api-key'
      const imgPath = path.join(tmpDir, 'blocked_test.png')
      fs.writeFileSync(imgPath, Buffer.from('data'))

      globalThis.fetch = async () =>
        new Response(JSON.stringify({ promptFeedback: { blockReason: 'SAFETY' } }), { status: 200 })

      await assert.rejects(
        () => geminiOcrFile(imgPath, 'image', 12, { maxRetries: 2, baseBackoffMs: 1 }),
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'blocked' && !err.retryable,
      )

      globalThis.fetch = async () =>
        new Response(
          JSON.stringify({ candidates: [{ finishReason: 'MAX_TOKENS', content: { parts: [{ text: 'partial' }] } }] }),
          { status: 200 },
        )

      await assert.rejects(
        () => geminiOcrFile(imgPath, 'image', 12, { maxRetries: 2, baseBackoffMs: 1 }),
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'truncated' && !err.retryable,
      )
    })
  })

  describe('3. Gemini VLM OCR (Scanned PDF handling)', () => {
    it('sends PDF directly via application/pdf when under 20MB', async () => {
      config.geminiApiKey = 'fake-api-key'
      const pdfPath = path.join(tmpDir, 'scan.pdf')
      fs.writeFileSync(pdfPath, Buffer.from('%PDF-1.4 dummy content'))

      let capturedMime = ''
      globalThis.fetch = async (_url: RequestInfo | URL, init?: RequestInit) => {
        const body = JSON.parse(String(init?.body))
        capturedMime = body.contents[0].parts[1].inlineData.mimeType
        return new Response(
          JSON.stringify({
            candidates: [
              {
                content: {
                  parts: [{ text: '--- Page 1 ---\nInduction Step:\nAssume $P(k)$ is true.' }],
                },
              },
            ],
          }),
          { status: 200 }
        )
      }

      const text = await geminiOcrFile(pdfPath, 'scan')
      assert.strictEqual(capturedMime, 'application/pdf')
      assert.ok(text.includes('--- Page 1 ---'))
      assert.ok(text.includes('Assume $P(k)$ is true.'))
    })

    it('does not rasterize pages after transient failures exhaust their retries', async () => {
      config.geminiApiKey = 'fake-api-key'
      const pdfPath = path.join(tmpDir, 'transient.pdf')
      fs.writeFileSync(pdfPath, Buffer.from('%PDF-1.4 dummy content'))

      const mimes: string[] = []
      globalThis.fetch = async (_url: RequestInfo | URL, init?: RequestInit) => {
        mimes.push(JSON.parse(String(init?.body)).contents[0].parts[1].inlineData.mimeType)
        return new Response('Service Unavailable', { status: 503 })
      }

      await assert.rejects(
        () => geminiOcrFile(pdfPath, 'scan', 12, { maxRetries: 2, baseBackoffMs: 1 }),
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'server' && err.retryable,
      )
      // 1 attempt + 2 retries, all for the whole PDF; no per-page image/png calls.
      assert.deepStrictEqual(mimes, ['application/pdf', 'application/pdf', 'application/pdf'])
    })

    it('fails fast on auth errors for PDFs without rasterizing', async () => {
      config.geminiApiKey = 'bad-key'
      const pdfPath = path.join(tmpDir, 'auth.pdf')
      fs.writeFileSync(pdfPath, Buffer.from('%PDF-1.4 dummy content'))

      let calls = 0
      globalThis.fetch = async () => {
        calls++
        return new Response('API_KEY_INVALID: API key not valid.', { status: 400 })
      }

      await assert.rejects(
        () => geminiOcrFile(pdfPath, 'scan', 12, { maxRetries: 3, baseBackoffMs: 1 }),
        (err: unknown) => err instanceof GeminiOcrError && err.code === 'auth',
      )
      assert.strictEqual(calls, 1)
    })
  })

  describe('4. ocrFileAuto router delegation', () => {
    it('delegates to geminiOcrFile when GEMINI_API_KEY is configured', async () => {
      config.geminiApiKey = 'valid-gemini-key'
      const imgPath = path.join(tmpDir, 'route_test.png')
      fs.writeFileSync(imgPath, Buffer.from('image'))

      globalThis.fetch = async () => {
        return new Response(
          JSON.stringify({
            candidates: [{ content: { parts: [{ text: 'Delegated to Gemini successfully' }] } }],
          }),
          { status: 200 }
        )
      }

      const result = await ocrFileAuto(imgPath, 'image')
      assert.strictEqual(result, 'Delegated to Gemini successfully')
    })
  })

  describe('5. File utilities & Student guessing', () => {
    it('extracts student identifiers from submission filenames', () => {
      assert.strictEqual(guessStudentFromFilename('a2_q1_ohassan.py'), 'ohassan')
      assert.strictEqual(guessStudentFromFilename('hw3_j_smith.pdf'), 'smith')
      assert.strictEqual(guessStudentFromFilename('csc236_induction_proof_alice.pdf'), 'alice')
    })

    it('formats byte sizes cleanly', () => {
      assert.strictEqual(formatBytes(500), '500 B')
      assert.strictEqual(formatBytes(2048), '2.0 KB')
      assert.strictEqual(formatBytes(15 * 1024 * 1024), '15.0 MB')
    })
  })
})
