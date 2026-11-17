import JSZip from 'jszip'

export interface PreparedFile {
  key: string
  name: string
  size: number
  kind: 'text' | 'pdf' | 'scan' | 'image'
  text: string
  images: Blob[]
  pages?: number
  error?: string
  /** The original bytes, uploaded so the server keeps the file and can OCR scans. */
  blob?: Blob
}

const TEXT_EXT = new Set([
  'txt', 'md', 'tex', 'py', 'java', 'c', 'h', 'cpp', 'hpp', 'cc', 'js', 'ts', 'jsx', 'tsx', 'hs', 'ml', 'mli', 'scm',
  'rkt', 'lisp', 'v', 'coq', 'lean', 'agda', 'sml', 'go', 'rs', 'rb', 'sh', 'sql', 'json', 'csv', 'r', 'm', 'jl', 'kt',
  'swift', 'scala', 'pl', 'asm', 's', 'html', 'css', 'xml', 'yaml', 'yml', 'ipynb', 'bib', 'rst', 'org',
])
const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'webp', 'gif'])

export const ACCEPT = '.py,.pdf,.txt,.zip,.tex,.md,.docx,.png,.jpg,.jpeg,.webp,.java,.c,.cpp,.hs,.ml,.js,.ts,.ipynb'

/** Text past this many characters is cut before grading and storage. */
export const MAX_CHARS = 60000

function ext(name: string) {
  const i = name.lastIndexOf('.')
  return i < 0 ? '' : name.slice(i + 1).toLowerCase()
}

function looksBinary(s: string) {
  const sample = s.slice(0, 4000)
  let bad = 0
  for (let i = 0; i < sample.length; i++) {
    const c = sample.charCodeAt(i)
    if (c === 0 || c === 0xfffd) bad++
  }
  return bad > 8
}

function notebookToText(raw: string) {
  try {
    const nb = JSON.parse(raw) as { cells?: { cell_type: string; source: string | string[] }[] }
    return (nb.cells ?? [])
      .map((c, i) => `# [${c.cell_type} cell ${i + 1}]\n` + (Array.isArray(c.source) ? c.source.join('') : c.source))
      .join('\n\n')
  } catch {
    return raw
  }
}

async function docxToText(buf: ArrayBuffer) {
  const zip = await JSZip.loadAsync(buf)
  const xml = await zip.file('word/document.xml')?.async('string')
  if (!xml) return ''
  return xml
    .replace(/<w:tab\/>/g, '\t')
    .replace(/<\/w:p>/g, '\n')
    .replace(/<w:br[^>]*\/>/g, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&apos;/g, "'")
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

let fileCounter = 0

async function prepareOne(name: string, size: number, buf: () => Promise<ArrayBuffer>, maxImages: number): Promise<PreparedFile[]> {
  const e = ext(name)
  const key = `${Date.now()}${fileCounter++}`
  const base = e === 'zip' ? { key, name, size } : { key, name, size, blob: new Blob([await buf()]) }
  try {
    if (e === 'zip') {
      const zip = await JSZip.loadAsync(await buf())
      const out: PreparedFile[] = []
      const entries = Object.values(zip.files).filter(f => !f.dir && !f.name.startsWith('__MACOSX/') && !/(^|\/)\./.test(f.name))
      for (const f of entries) {
        const inner = f.name.split('/').pop() || f.name
        const data = await f.async('arraybuffer')
        out.push(...(await prepareOne(inner, data.byteLength, async () => data, maxImages)))
      }
      return out
    }
    if (e === 'pdf') {
      const { readPdf } = await import('./pdf')
      const r = await readPdf(await buf(), maxImages)
      // Scans have no text layer: the server reads them with OCR.
      if (r.scanned) return [{ ...base, kind: 'scan', text: '', images: r.images, pages: r.pages }]
      return [{ ...base, kind: 'pdf', text: r.text.slice(0, MAX_CHARS), images: [], pages: r.pages }]
    }
    if (IMAGE_EXT.has(e)) {
      const b = new Blob([await buf()], { type: e === 'jpg' ? 'image/jpeg' : `image/${e}` })
      return [{ ...base, kind: 'image', text: '', images: [b] }]
    }
    if (e === 'docx') {
      const t = await docxToText(await buf())
      return [{ ...base, kind: 'text', text: t.slice(0, MAX_CHARS), images: [], error: t ? undefined : 'Empty Word document.' }]
    }
    const raw = new TextDecoder('utf-8', { fatal: false }).decode(await buf())
    if (!TEXT_EXT.has(e) && looksBinary(raw)) {
      return [{ ...base, kind: 'text', text: '', images: [], error: `Unsupported file type (.${e || 'unknown'}).` }]
    }
    const text = e === 'ipynb' ? notebookToText(raw) : raw
    return [{ ...base, kind: 'text', text: text.slice(0, MAX_CHARS), images: [], error: text.trim() ? undefined : 'File is empty.' }]
  } catch (err) {
    return [{ ...base, kind: 'text', text: '', images: [], error: 'Could not read this file: ' + (err instanceof Error ? err.message : String(err)) }]
  }
}

export async function prepareFiles(files: File[], maxImages: number): Promise<PreparedFile[]> {
  const out: PreparedFile[] = []
  for (const f of files) out.push(...(await prepareOne(f.name, f.size, () => f.arrayBuffer(), maxImages)))
  return out
}

/** Read a plain text file (rubric or roster upload). */
export async function readText(file: File) {
  const e = ext(file.name)
  if (e === 'pdf') {
    const { readPdf } = await import('./pdf')
    const r = await readPdf(await file.arrayBuffer(), 0)
    return r.text
  }
  if (e === 'docx') return docxToText(await file.arrayBuffer())
  return file.text()
}

/** Guess a student label from a file name like "a2_q1_ohassan.py" -> "ohassan". */
export function guessStudentFromFilename(name: string) {
  const stem = name.replace(/\.[^.]+$/, '')
  const parts = stem.split(/[_\-\s.]+/).filter(Boolean)
  const generic = /^(a\d+|q\d+|hw\d*|assignment\d*|problem\d*|ps\d+|final|submission|v\d+|csc\d+|mat\d+|pset\d*|lab\d*|ex\d+)$/i
  const cand = parts.filter(p => !generic.test(p) && !/^\d+$/.test(p))
  return cand.length ? cand[cand.length - 1] : stem
}

export function formatBytes(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
