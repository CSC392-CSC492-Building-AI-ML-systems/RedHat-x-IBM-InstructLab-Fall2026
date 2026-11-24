import { useEffect, useRef, useState } from 'react'
import type { Submission } from '../lib/types'
import { isPdfRenderCancelled, openPdf, renderPdfPage, type PDFDocumentProxy } from '../lib/pdf'
import { Notice, Spinner } from './ui'

interface DocumentViewerProps {
  submissionId: string
  fileName: string
  fileKind: Submission['fileKind']
  storedFile?: string
  queueState?: Submission['queueState']
  maxHeight?: number
}

const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5]

function clampZoom(z: number) {
  return Math.max(0.4, Math.min(2.5, Math.round(z * 100) / 100))
}

function nextZoomStep(current: number, dir: 1 | -1) {
  if (dir > 0) return ZOOM_STEPS.find(s => s > current + 0.02) ?? 2.5
  return [...ZOOM_STEPS].reverse().find(s => s < current - 0.02) ?? 0.5
}

export default function DocumentViewer({
  submissionId,
  fileName,
  fileKind,
  storedFile,
  queueState,
  maxHeight = 520,
}: DocumentViewerProps) {
  const inlineUrl = `/api/files/${encodeURIComponent(submissionId)}?inline=1`
  const downloadUrl = `/api/files/${encodeURIComponent(submissionId)}`

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [errorMsg, setErrorMsg] = useState('')
  const [imgUrl, setImgUrl] = useState<string | null>(null)
  const [imgSize, setImgSize] = useState<{ width: number; height: number } | null>(null)
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)

  const [fitWidth, setFitWidth] = useState(true)
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [containerWidth, setContainerWidth] = useState(560)

  const viewportRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  useEffect(() => {
    const el = viewportRef.current
    if (!el) return
    const update = () => {
      const w = el.clientWidth
      if (w > 0) setContainerWidth(w)
    }
    update()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    setFitWidth(true)
    setZoom(1)
    setRotation(0)
    setCurrentPage(1)
    setNumPages(0)
    setImgSize(null)
    setErrorMsg('')

    if (!storedFile || fileKind === 'text') {
      setStatus('error')
      setErrorMsg('The original file is not stored on the server.')
      return
    }

    const ac = new AbortController()
    let active = true
    let createdUrl: string | null = null
    let loadedDoc: PDFDocumentProxy | null = null

    setStatus('loading')
    setImgUrl(null)
    setPdfDoc(null)

    ;(async () => {
      try {
        const res = await fetch(inlineUrl, { credentials: 'same-origin', signal: ac.signal })
        if (!res.ok) {
          let msg = `Could not load original file (HTTP ${res.status}).`
          try {
            const body = await res.json() as { message?: string }
            if (body?.message) msg = body.message
          } catch { /* non-JSON error */ }
          throw new Error(msg)
        }

        if (fileKind === 'image') {
          const blob = await res.blob()
          if (!active) return
          createdUrl = URL.createObjectURL(blob)
          setImgUrl(createdUrl)
          setStatus('ready')
          return
        }

        const buf = await res.arrayBuffer()
        if (!active) return
        loadedDoc = await openPdf(buf)
        if (!active) {
          await loadedDoc.destroy()
          return
        }
        setPdfDoc(loadedDoc)
        setNumPages(loadedDoc.numPages)
        setStatus('ready')
      } catch (err) {
        if (!active || (err instanceof Error && err.name === 'AbortError')) return
        setErrorMsg(err instanceof Error ? err.message : 'Could not render this document.')
        setStatus('error')
      }
    })()

    return () => {
      active = false
      ac.abort()
      if (createdUrl) URL.revokeObjectURL(createdUrl)
      if (loadedDoc) void loadedDoc.destroy()
    }
  }, [submissionId, fileKind, storedFile, inlineUrl])

  function jumpToPage(pageNum: number) {
    const clamped = Math.max(1, Math.min(numPages, pageNum))
    setCurrentPage(clamped)
    const el = pageRefs.current.get(clamped)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function stepZoom(dir: 1 | -1) {
    setFitWidth(false)
    setZoom(z => nextZoomStep(z, dir))
  }

  const isPdf = fileKind === 'pdf' || fileKind === 'scan'
  const effectiveZoomLabel = fitWidth ? 'Fit' : `${Math.round(zoom * 100)}%`
  const btnCls = 'px-2 py-1 text-[11px] rounded transition-opacity hover:opacity-80 disabled:opacity-40'
  const btnStyle = { background: 'var(--background)', color: 'var(--foreground)', border: '1px solid var(--border)' }

  if (!storedFile) {
    return (
      <Notice kind="info">
        The original file is not stored on the server for this submission.
        {queueState === 'ocr' && ' OCR is currently in progress.'}
      </Notice>
    )
  }

  return (
    <div className="rounded overflow-hidden flex flex-col" style={{ border: '1px solid var(--border)', background: 'var(--secondary)' }}>
      {/* Toolbar */}
      <div
        className="px-3 py-2 flex flex-wrap items-center justify-between gap-2 border-b"
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="mono text-[10px] uppercase tracking-widest px-1.5 py-0.5 rounded" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>
            {fileKind === 'image' ? 'Image' : fileKind === 'scan' ? 'Scan PDF' : 'PDF'}
          </span>
          {isPdf && numPages > 0 && (
            <div className="flex items-center gap-1">
              <button type="button" className={btnCls} style={btnStyle} disabled={currentPage <= 1} onClick={() => jumpToPage(currentPage - 1)} aria-label="Previous page">
                ‹
              </button>
              <span className="mono text-[11px] px-1.5" style={{ color: 'var(--foreground)' }}>
                {currentPage} / {numPages}
              </span>
              <button type="button" className={btnCls} style={btnStyle} disabled={currentPage >= numPages} onClick={() => jumpToPage(currentPage + 1)} aria-label="Next page">
                ›
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          <button type="button" className={btnCls} style={btnStyle} onClick={() => stepZoom(-1)} aria-label="Zoom out" title="Zoom out">
            −
          </button>
          <button
            type="button"
            className={`${btnCls} mono min-w-[46px] text-center`}
            style={fitWidth ? { background: 'var(--primary)', color: 'var(--primary-foreground)', border: '1px solid var(--primary)' } : btnStyle}
            onClick={() => { setFitWidth(f => !f); if (!fitWidth) setZoom(1) }}
            title="Toggle fit to width"
          >
            {effectiveZoomLabel}
          </button>
          <button type="button" className={btnCls} style={btnStyle} onClick={() => stepZoom(1)} aria-label="Zoom in" title="Zoom in">
            +
          </button>
          <button
            type="button"
            className={btnCls}
            style={btnStyle}
            onClick={() => setRotation(r => (r + 90) % 360)}
            aria-label="Rotate 90 degrees"
            title="Rotate 90° clockwise"
          >
            ↻
          </button>
          <a
            href={inlineUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={btnCls}
            style={btnStyle}
            title="Open original in a new tab"
          >
            Open ↗
          </a>
        </div>
      </div>

      {/* Document surface */}
      <div
        ref={viewportRef}
        className="overflow-auto p-3"
        style={{ maxHeight, minHeight: 240 }}
      >
        {status === 'loading' && (
          <div className="flex items-center justify-center gap-2 py-16 text-xs" style={{ color: 'var(--muted-foreground)' }}>
            <Spinner size={14} /> Loading original document…
          </div>
        )}

        {status === 'error' && (
          <div className="p-2">
            <Notice kind="error" className="mb-3">{errorMsg || 'Failed to load original document.'}</Notice>
            <a
              href={downloadUrl}
              download={fileName}
              className="px-3 py-1.5 text-xs rounded inline-flex items-center hover:opacity-80"
              style={{ background: 'var(--background)', color: 'var(--foreground)', border: '1px solid var(--border)' }}
            >
              Download original ({fileName})
            </a>
          </div>
        )}

        {status === 'ready' && fileKind === 'image' && imgUrl && (
          <ImageSurface
            src={imgUrl}
            alt={fileName}
            fitWidth={fitWidth}
            zoom={zoom}
            rotation={rotation}
            containerWidth={Math.max(180, containerWidth - 24)}
            naturalSize={imgSize}
            onLoadSize={setImgSize}
            onError={() => {
              setErrorMsg('Could not decode this image in the browser.')
              setStatus('error')
            }}
          />
        )}

        {status === 'ready' && isPdf && pdfDoc && (
          <div className="flex flex-col items-center gap-3">
            {Array.from({ length: numPages }, (_, i) => i + 1).map(pageNum => (
              <PdfPageCard
                key={`${submissionId}-p${pageNum}`}
                doc={pdfDoc}
                pageNum={pageNum}
                totalPages={numPages}
                fitWidth={fitWidth}
                zoom={zoom}
                rotation={rotation}
                containerWidth={Math.max(180, containerWidth - 28)}
                scrollRoot={viewportRef.current}
                registerRef={el => {
                  if (el) pageRefs.current.set(pageNum, el)
                  else pageRefs.current.delete(pageNum)
                }}
                onVisible={() => setCurrentPage(pageNum)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ImageSurface({
  src,
  alt,
  fitWidth,
  zoom,
  rotation,
  containerWidth,
  naturalSize,
  onLoadSize,
  onError,
}: {
  src: string
  alt: string
  fitWidth: boolean
  zoom: number
  rotation: number
  containerWidth: number
  naturalSize: { width: number; height: number } | null
  onLoadSize: (s: { width: number; height: number }) => void
  onError: () => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  useEffect(() => {
    if (rotation === 0 || !naturalSize || !canvasRef.current || !imgRef.current) return
    const img = imgRef.current
    const canvas = canvasRef.current
    const swapped = rotation === 90 || rotation === 270
    const baseW = swapped ? naturalSize.height : naturalSize.width
    const baseH = swapped ? naturalSize.width : naturalSize.height
    const scale = fitWidth ? Math.min(1.5, containerWidth / baseW) : clampZoom(zoom)
    const cssW = Math.max(1, Math.round(baseW * scale))
    const cssH = Math.max(1, Math.round(baseH * scale))
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    canvas.width = Math.round(cssW * dpr)
    canvas.height = Math.round(cssH * dpr)
    canvas.style.width = `${cssW}px`
    canvas.style.height = `${cssH}px`
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.save()
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.translate(canvas.width / 2, canvas.height / 2)
    ctx.rotate((rotation * Math.PI) / 180)
    const drawW = Math.round(naturalSize.width * scale * dpr)
    const drawH = Math.round(naturalSize.height * scale * dpr)
    ctx.drawImage(img, -drawW / 2, -drawH / 2, drawW, drawH)
    ctx.restore()
  }, [rotation, naturalSize, fitWidth, zoom, containerWidth])

  return (
    <div className="flex justify-center">
      <img
        ref={imgRef}
        src={src}
        alt={alt}
        onLoad={e => {
          const el = e.currentTarget
          if (el.naturalWidth && el.naturalHeight) onLoadSize({ width: el.naturalWidth, height: el.naturalHeight })
        }}
        onError={onError}
        className={rotation === 0 ? 'rounded shadow-sm bg-white block' : 'hidden'}
        style={
          rotation === 0
            ? fitWidth
              ? { maxWidth: '100%', height: 'auto' }
              : { width: naturalSize ? Math.round(naturalSize.width * clampZoom(zoom)) : undefined, maxWidth: 'none', height: 'auto' }
            : undefined
        }
      />
      {rotation !== 0 && naturalSize && (
        <canvas ref={canvasRef} className="rounded shadow-sm bg-white block" aria-label={alt} />
      )}
    </div>
  )
}

function PdfPageCard({
  doc,
  pageNum,
  totalPages,
  fitWidth,
  zoom,
  rotation,
  containerWidth,
  scrollRoot,
  registerRef,
  onVisible,
}: {
  doc: PDFDocumentProxy
  pageNum: number
  totalPages: number
  fitWidth: boolean
  zoom: number
  rotation: number
  containerWidth: number
  scrollRoot: HTMLDivElement | null
  registerRef: (el: HTMLDivElement | null) => void
  onVisible: () => void
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const onVisibleRef = useRef(onVisible)
  onVisibleRef.current = onVisible
  const [shouldRender, setShouldRender] = useState(pageNum <= 2)
  const [pageError, setPageError] = useState(false)
  const [baseSize, setBaseSize] = useState<{ width: number; height: number } | null>(null)

  useEffect(() => {
    let active = true
    doc.getPage(pageNum).then(page => {
      if (!active) return
      const rot = ((page.rotate || 0) + rotation) % 360
      const vp = page.getViewport({ scale: 1, rotation: rot })
      setBaseSize({ width: vp.width, height: vp.height })
    }).catch(() => { /* doc destroyed */ })
    return () => { active = false }
  }, [doc, pageNum, rotation])

  useEffect(() => {
    const el = wrapRef.current
    if (!el || typeof IntersectionObserver === 'undefined') {
      setShouldRender(true)
      return
    }
    const renderObserver = new IntersectionObserver(
      entries => {
        if (entries.some(e => e.isIntersecting)) setShouldRender(true)
      },
      { root: scrollRoot, rootMargin: '350px 0px' },
    )
    renderObserver.observe(el)

    const activeObserver = new IntersectionObserver(
      entries => {
        if (entries.some(e => e.isIntersecting)) onVisibleRef.current()
      },
      { root: scrollRoot, threshold: 0.5 },
    )
    activeObserver.observe(el)

    return () => {
      renderObserver.disconnect()
      activeObserver.disconnect()
    }
  }, [scrollRoot])

  const targetScale = baseSize
    ? fitWidth
      ? Math.max(0.4, Math.min(2.5, containerWidth / baseSize.width))
      : clampZoom(zoom)
    : 1

  useEffect(() => {
    if (!shouldRender || !canvasRef.current) return
    const canvas = canvasRef.current
    const ac = new AbortController()
    let active = true
    setPageError(false)

    ;(async () => {
      try {
        const page = await doc.getPage(pageNum)
        if (!active || ac.signal.aborted) return
        const dpr = Math.min(2, window.devicePixelRatio || 1)
        await renderPdfPage(page, canvas, {
          scale: targetScale,
          rotation,
          dpr,
          signal: ac.signal,
        })
      } catch (err) {
        if (!active || ac.signal.aborted || isPdfRenderCancelled(err) || (err instanceof Error && err.name === 'AbortError')) return
        setPageError(true)
      }
    })()

    return () => {
      active = false
      ac.abort()
    }
  }, [doc, pageNum, shouldRender, targetScale, rotation])

  const estW = baseSize ? Math.round(baseSize.width * targetScale) : undefined
  const estH = baseSize ? Math.round(baseSize.height * targetScale) : 320

  return (
    <div
      ref={el => {
        wrapRef.current = el
        registerRef(el)
      }}
      className="flex flex-col items-center gap-1 max-w-full"
    >
      <div
        className="rounded shadow-sm bg-white overflow-hidden flex items-center justify-center"
        style={{ minWidth: estW ? Math.min(estW, containerWidth) : 200, minHeight: estH }}
      >
        {pageError ? (
          <div className="p-4 text-xs" style={{ color: '#dc2626' }}>Could not render page {pageNum}.</div>
        ) : (
          <canvas ref={canvasRef} className="block" aria-label={`Page ${pageNum} of ${totalPages}`} />
        )}
      </div>
      {totalPages > 1 && (
        <span className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
          Page {pageNum} of {totalPages}
        </span>
      )}
    </div>
  )
}
