import * as pdfjs from 'pdfjs-dist'
import PdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker&inline'

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

/** Extract text from a PDF. If it has little or no text layer (a scan or a photo of
    handwritten work), render the first pages to JPEG so Claude can read them. */
export async function readPdf(buf: ArrayBuffer, maxImages: number): Promise<PdfRead> {
  ensureWorker()
  const doc = await pdfjs.getDocument({ data: new Uint8Array(buf) }).promise
  const parts: string[] = []
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
      const base = page.getViewport({ scale: 1 })
      const scale = Math.min(2, 1600 / Math.max(base.width, base.height))
      const vp = page.getViewport({ scale })
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(vp.width)
      canvas.height = Math.round(vp.height)
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = '#fff'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      await page.render({ canvasContext: ctx, viewport: vp }).promise
      const blob = await new Promise<Blob | null>(r => canvas.toBlob(r, 'image/jpeg', 0.85))
      if (blob) images.push(blob)
    }
  }
  await doc.destroy()
  return { text: scanned ? '' : text, pages: doc.numPages, scanned, images }
}
