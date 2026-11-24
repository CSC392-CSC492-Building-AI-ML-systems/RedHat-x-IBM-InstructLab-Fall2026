import * as pdfjs from 'pdfjs-dist'
import type { PDFDocumentProxy, PDFPageProxy } from 'pdfjs-dist'
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker&inline'

export type { PDFDocumentProxy, PDFPageProxy }

let workerReady = false
function ensureWorker() {
  if (workerReady) return
  pdfjs.GlobalWorkerOptions.workerPort = new PdfWorker()
  workerReady = true
}

export interface PdfRead {
  text: string
  pages: number
  scanned: boolean
  images: Blob[]
}

export interface RenderPdfPageOptions {
  /** Explicit CSS-pixel scale relative to PDF points (72 DPI). Overrides maxDimension. */
  scale?: number
  /** Cap the longest rendered dimension in pixels when scale is omitted. */
  maxDimension?: number
  /** Additional clockwise rotation in degrees (0, 90, 180, 270). */
  rotation?: number
  /** Device pixel ratio for sharp rendering on HiDPI displays. */
  dpr?: number
  /** AbortSignal to cancel an in-flight render task. */
  signal?: AbortSignal
}

/** Open a PDF document from raw bytes using the shared PDF.js inline worker. */
export async function openPdf(data: ArrayBuffer | Uint8Array): Promise<PDFDocumentProxy> {
  ensureWorker()
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data)
  return pdfjs.getDocument({ data: bytes }).promise
}

/** Check whether an error came from cancelling an in-flight PDF.js render task. */
export function isPdfRenderCancelled(err: unknown): boolean {
  return err instanceof Error && err.name === 'RenderingCancelledException'
}

/** Render a single PDF page onto a canvas with a white paper background. */
export async function renderPdfPage(
  page: PDFPageProxy,
  canvas: HTMLCanvasElement,
  opts: RenderPdfPageOptions = {},
): Promise<{ width: number; height: number }> {
  const rotation = ((page.rotate || 0) + (opts.rotation ?? 0)) % 360
  const base = page.getViewport({ scale: 1, rotation })
  const scale = opts.scale ?? (opts.maxDimension ? Math.min(2, opts.maxDimension / Math.max(base.width, base.height)) : 1)
  const dpr = Math.max(1, opts.dpr ?? 1)
  const cssVp = page.getViewport({ scale, rotation })
  const renderVp = page.getViewport({ scale: scale * dpr, rotation })

  const cssWidth = Math.max(1, Math.round(cssVp.width))
  const cssHeight = Math.max(1, Math.round(cssVp.height))
  canvas.width = Math.max(1, Math.round(renderVp.width))
  canvas.height = Math.max(1, Math.round(renderVp.height))
  if (opts.dpr && opts.dpr > 1) {
    canvas.style.width = `${cssWidth}px`
    canvas.style.height = `${cssHeight}px`
  } else {
    canvas.style.width = ''
    canvas.style.height = ''
  }

  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas 2D context is unavailable.')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  if (opts.signal?.aborted) {
    throw new DOMException('Render aborted', 'AbortError')
  }

  const task = page.render({ canvasContext: ctx, viewport: renderVp })
  const onAbort = () => task.cancel()
  opts.signal?.addEventListener('abort', onAbort, { once: true })
  try {
    await task.promise
  } finally {
    opts.signal?.removeEventListener('abort', onAbort)
  }
  return { width: cssWidth, height: cssHeight }
}

/** Extract text from a PDF. Optionally render scanned pages to JPEG blobs. */
export async function readPdf(buf: ArrayBuffer, maxImages = 0): Promise<PdfRead> {
  const doc = await openPdf(buf)
  const parts: string[] = []
  try {
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i)
      const tc = await page.getTextContent()
      let line = ''
      const lines: string[] = []
      let lastY: number | null = null
      for (const item of tc.items as Array<{ str?: string; transform?: number[]; hasEOL?: boolean }>) {
        if (typeof item.str !== 'string') continue
        const y = item.transform ? item.transform[5] : null
        if (lastY !== null && y !== null && Math.abs(y - lastY) > 2 && line) {
          lines.push(line)
          line = ''
        }
        line += item.str
        if (item.hasEOL) { lines.push(line); line = '' }
        lastY = y
      }
      if (line) lines.push(line)
      parts.push(`--- Page ${i} ---\n` + lines.join('\n'))
    }
    const text = parts.join('\n\n')
    const letters = text.replace(/--- Page \d+ ---/g, '').replace(/\s+/g, '').length
    const scanned = letters < 80 * doc.numPages
    const images: Blob[] = []
    if (scanned && maxImages > 0) {
      for (let i = 1; i <= Math.min(doc.numPages, maxImages); i++) {
        const page = await doc.getPage(i)
        const canvas = document.createElement('canvas')
        await renderPdfPage(page, canvas, { maxDimension: 1600 })
        const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/jpeg', 0.85))
        if (blob) images.push(blob)
      }
    }
    return { text: scanned ? '' : text, pages: doc.numPages, scanned, images }
  } finally {
    await doc.destroy()
  }
}
