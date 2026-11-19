import { useEffect, useMemo, useRef, useState } from 'react'
import type { Submission, View } from '../lib/types'
import { useApp } from '../context'
import { ACCEPT, formatBytes, guessStudentFromFilename, prepareFiles, type PreparedFile } from '../lib/files'
import { matchRoster } from '../lib/grading'
import { ApiError } from '../lib/api'
import { fmtScore, scoreColor } from '../lib/format'
import { Bar, Button, Card, Checkbox, Label, Notice, Spinner, StarIcon, UploadIcon } from './ui'
import ReviewModal from './ReviewModal'
import ModelBadge from './ModelBadge'

type Stage = 'upload' | 'config' | 'running' | 'done'

interface Staged extends PreparedFile {
  student: string
  studentId: string
  email: string
}

const KIND_LABEL = { text: 'text', pdf: 'PDF', scan: 'scan · OCR', image: 'image · OCR' } as const

function rowStatus(s: Submission, online: boolean): { label: string; color: string } {
  if (s.status === 'graded') return { label: 'Graded', color: '#16a34a' }
  if (s.status === 'review') return { label: 'Needs Review', color: '#d97706' }
  if (s.status === 'error') return { label: 'Failed', color: '#ef4444' }
  if (s.queueState === 'ocr') return { label: 'Reading scan…', color: '#1e3765' }
  if (s.queueState === 'grading') return { label: 'Grading…', color: '#1e3765' }
  return online ? { label: 'Queued', color: '#6b7a99' } : { label: 'Waiting for model', color: '#6b7a99' }
}

function loadBatches(key: string): string[] {
  try { return JSON.parse(localStorage.getItem(key) ?? '[]') } catch { return [] }
}

export default function GradingSession({ setActiveView }: { setActiveView: (v: View) => void }) {
  const { rubrics, settings, me, submissions, saveSubmission, notify, model, uploadBatch, regrade, cancelBatch, role, ocr } = useApp()

  const storageKey = `gradeai-batches-${me.id}`
  const [staged, setStaged] = useState<Staged[]>([])
  const [batchIds, setBatchIds] = useState<string[]>(() => loadBatches(storageKey))
  const [reading, setReading] = useState(false)
  const [uploading, setUploading] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [reviewId, setReviewId] = useState<string | null>(null)
  const [flagLow, setFlagLow] = useState(true)
  const [detailed, setDetailed] = useState(true)
  const [plagiarism, setPlagiarism] = useState(settings.plagiarism)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { try { localStorage.setItem(storageKey, JSON.stringify(batchIds.slice(-20))) } catch { /* private mode */ } }, [batchIds, storageKey])
  useEffect(() => { setPlagiarism(settings.plagiarism) }, [settings.plagiarism])

  const sortedRubrics = useMemo(
    () => [...rubrics].sort((a, b) => Number(b.assignment === settings.currentAssignment) - Number(a.assignment === settings.currentAssignment)),
    [rubrics, settings.currentAssignment],
  )
  const [rubricId, setRubricId] = useState<string>('')
  useEffect(() => {
    if (!rubricId || !rubrics.find(r => r.id === rubricId)) setRubricId(sortedRubrics[0]?.id ?? '')
  }, [rubrics, rubricId, sortedRubrics])
  const rubric = rubrics.find(r => r.id === rubricId) ?? null

  const rows = useMemo(
    () => submissions.filter(s => s.batchId && batchIds.includes(s.batchId)).sort((a, b) => a.submittedAt - b.submittedAt || a.file.localeCompare(b.file)),
    [submissions, batchIds],
  )
  const pendingRows = rows.filter(r => r.status === 'pending')
  const stage: Stage = uploading !== null || pendingRows.length ? 'running' : staged.length ? 'config' : rows.length ? 'done' : 'upload'

  async function addFiles(fileList: FileList | File[] | null) {
    if (!fileList || !fileList.length) return
    setReading(true)
    try {
      const prepared = await prepareFiles(Array.from(fileList), 0)
      const existing = new Set(staged.map(i => i.name))
      const next: Staged[] = prepared.filter(p => !existing.has(p.name)).map(p => {
        const r = matchRoster(settings.roster, { fileName: p.name })
        return { ...p, student: r?.name ?? guessStudentFromFilename(p.name), studentId: r?.studentId ?? '', email: r?.email ?? '' }
      })
      if (next.length < prepared.length) notify(`${prepared.length - next.length} duplicate file(s) skipped.`, 'warn')
      const scans = next.filter(f => (f.kind === 'scan' || f.kind === 'image') && !f.error).length
      if (scans && !ocr.tesseract) notify(`${scans} scanned file(s) need OCR, which isn't installed on this computer. They will fail until you run: brew install tesseract poppler`, 'warn')
      setStaged(list => [...list, ...next])
    } finally {
      setReading(false)
    }
  }

  async function startGrading() {
    const ready = staged.filter(s => !s.error)
    if (!ready.length) {
      if (!staged.length) inputRef.current?.click()
      else notify('None of these files can be read. Remove them and add others.', 'warn')
      return
    }
    if (!rubric) { notify('Choose a rubric first.', 'warn'); return }
    setUploading(0)
    try {
      const { batchId, ids } = await uploadBatch(
        rubric.id,
        { flagLow, detailed, plagiarism },
        ready.map(f => ({ key: f.key, name: f.name, student: f.student, studentId: f.studentId, email: f.email, kind: f.kind, text: f.text, blob: f.blob })),
        pct => setUploading(pct),
      )
      setBatchIds(b => [...b, batchId])
      setStaged(list => list.filter(s => s.error))
      notify(model.online
        ? `${ids.length} file${ids.length === 1 ? '' : 's'} queued — the model is grading now.`
        : `${ids.length} file${ids.length === 1 ? '' : 's'} queued. They'll be graded when the Fir model connects.`)
    } catch (e) {
      notify(e instanceof ApiError ? e.message : 'Upload failed. Check your connection and try again.', 'error')
    } finally {
      setUploading(null)
    }
  }

  async function stop() {
    const ids = [...new Set(pendingRows.map(r => r.batchId!).filter(Boolean))]
    let n = 0
    for (const b of ids) n += await cancelBatch(b).catch(() => 0)
    notify(n ? `${n} waiting file${n === 1 ? '' : 's'} removed from the queue.` : 'Files already being graded will finish.', n ? 'ok' : 'warn')
  }

  async function retryFailed() {
    const failed = rows.filter(r => r.status === 'error')
    for (const r of failed) await regrade(r.id).catch(() => undefined)
    notify(`${failed.length} file${failed.length === 1 ? '' : 's'} queued again.`)
  }

  function clearList() {
    setStaged([])
    setBatchIds([])
    setSelectedId(null)
  }

  const selected = submissions.find(s => s.id === selectedId) ?? null
  const doneCount = rows.filter(f => f.status === 'graded').length
  const reviewCount = rows.filter(f => f.status === 'review').length
  const errorCount = rows.filter(f => f.status === 'error').length
  const readyCount = staged.filter(s => !s.error).length

  return (
    <div className="p-4 md:p-8 max-w-screen-xl mx-auto">
      <div className="mb-8">
        <div className="mono text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted-foreground)' }}>AI Grading Engine</div>
        <h1 className="text-2xl tracking-tight" style={{ color: 'var(--foreground)' }}>Grade Batch</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          Upload student files, select a rubric, and let the fine-tuned model grade at scale.
        </p>
      </div>

      {/* Stage tabs */}
      <div className="flex items-center gap-0 mb-8 border-b overflow-x-auto" style={{ borderColor: 'var(--border)' }}>
        {(['upload', 'config', 'running', 'done'] as Stage[]).map((s, i) => (
          <div key={s} className="flex items-center shrink-0">
            <div
              className="pb-3 px-4 text-sm transition-all relative"
              aria-current={stage === s ? 'step' : undefined}
              style={{ color: stage === s ? 'var(--primary)' : 'var(--muted-foreground)', borderBottom: stage === s ? '2px solid var(--primary)' : '2px solid transparent', marginBottom: -1 }}
            >
              <span className="mono text-[10px] mr-1.5">{i + 1}.</span>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </div>
            {i < 3 && <span className="text-xs mx-1" style={{ color: 'var(--border)' }}>›</span>}
          </div>
        ))}
      </div>

      {!model.online && pendingRows.length > 0 && (
        <Notice className="mb-6">
          The grading model is offline, so {pendingRows.length} file{pendingRows.length === 1 ? ' is' : 's are'} waiting. Grading starts on its own when the Fir model connects (npm run model:connect). Keep GradeAI running; you can close this page.
        </Notice>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); addFiles(e.dataTransfer.files) }}
            onClick={() => uploading === null && inputRef.current?.click()}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inputRef.current?.click() } }}
            role="button"
            tabIndex={0}
            aria-label="Upload student files"
            className="rounded border-2 border-dashed p-10 flex flex-col items-center justify-center cursor-pointer transition-all text-center"
            style={{ borderColor: dragOver ? 'var(--primary)' : 'var(--border)', background: dragOver ? 'rgba(59,111,255,0.04)' : 'var(--card)' }}
          >
            <input ref={inputRef} type="file" multiple className="hidden" accept={ACCEPT} onChange={e => { addFiles(e.target.files); e.target.value = '' }} />
            {reading ? <div className="mb-3"><Spinner size={28} /></div> : <div className="mb-3"><UploadIcon /></div>}
            <div className="text-sm mb-1" style={{ color: 'var(--foreground)' }}>{reading ? 'Reading files…' : 'Drop student files here'}</div>
            <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
              .py, .pdf, .txt, .tex, .docx, scans or a .zip of all of them — up to 500 files per batch
            </div>
          </div>

          {(staged.length > 0 || rows.length > 0) && (
            <Card className="overflow-hidden">
              <div className="px-5 py-3 flex flex-wrap items-center justify-between gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
                <span className="text-sm" style={{ color: 'var(--foreground)' }}>
                  {staged.length ? `${staged.length} ready to upload` : ''}{staged.length && rows.length ? ' · ' : ''}{rows.length ? `${rows.length} uploaded` : ''}
                </span>
                <div className="flex items-center gap-3">
                  <span className="mono text-[11px]" style={{ color: 'var(--muted-foreground)' }}>
                    {doneCount} graded · {reviewCount} review{pendingRows.length ? ` · ${pendingRows.length} in queue` : ''}{errorCount ? ` · ${errorCount} failed` : ''}
                  </span>
                  {uploading === null && !pendingRows.length && (
                    <button type="button" onClick={clearList} className="mono text-[11px] hover:opacity-70" style={{ color: 'var(--primary)' }}>Clear</button>
                  )}
                </div>
              </div>
              <div className="max-h-[520px] overflow-y-auto">
                {staged.map((f, i) => (
                  <div key={f.key} className="flex items-center gap-3 px-5 py-3" style={{ borderBottom: i < staged.length - 1 || rows.length ? '1px solid var(--border)' : 'none' }}>
                    <div className="flex-1 min-w-0">
                      <input
                        aria-label={`Student for ${f.name}`}
                        value={f.student}
                        onChange={e => setStaged(l => l.map(x => (x.key === f.key ? { ...x, student: e.target.value } : x)))}
                        className="text-sm bg-transparent outline-none w-full rounded px-1 -mx-1 hover:bg-[var(--card)] focus:bg-[var(--card)]"
                        style={{ color: 'var(--foreground)' }}
                      />
                      <div className="mono text-[11px] truncate" style={{ color: f.error ? '#ef4444' : 'var(--muted-foreground)' }}>
                        {f.error ?? `${f.name} · ${formatBytes(f.size)} · ${KIND_LABEL[f.kind]}${f.pages ? ` · ${f.pages}p` : ''}`}
                      </div>
                    </div>
                    <span className="mono text-[10px] px-2 py-0.5 rounded shrink-0" style={{ background: f.error ? 'rgba(239,68,68,0.1)' : 'var(--secondary)', color: f.error ? '#ef4444' : 'var(--muted-foreground)' }}>
                      {f.error ? "Can't read" : 'Ready'}
                    </span>
                    <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setStaged(l => l.filter(x => x.key !== f.key))} className="w-5 h-5 flex items-center justify-center rounded hover:bg-[var(--card)] shrink-0" style={{ color: 'var(--muted-foreground)' }}>×</button>
                  </div>
                ))}
                {rows.map((s, i) => {
                  const st = rowStatus(s, model.online)
                  const canOpen = s.score !== null
                  return (
                    <div
                      key={s.id}
                      onClick={() => canOpen && setSelectedId(s.id === selectedId ? null : s.id)}
                      className={`flex items-center gap-3 px-5 py-3 transition-colors ${canOpen ? 'cursor-pointer hover:bg-[var(--secondary)]' : ''}`}
                      style={{ borderBottom: i < rows.length - 1 ? '1px solid var(--border)' : 'none', background: selectedId === s.id ? 'var(--secondary)' : 'transparent' }}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="text-sm truncate" style={{ color: 'var(--foreground)' }}>{s.student}</div>
                        <div className="mono text-[11px] truncate" style={{ color: s.status === 'error' ? '#ef4444' : 'var(--muted-foreground)' }}>
                          {s.status === 'error' && s.error ? s.error : `${s.file} · ${formatBytes(s.fileSize)} · ${KIND_LABEL[s.fileKind]}`}
                        </div>
                      </div>
                      {s.queueState === 'grading' && <div className="w-24 shrink-0"><Bar value={60} /></div>}
                      {s.score !== null && (
                        <span className="mono text-xs shrink-0" style={{ color: scoreColor(s.score, s.total) }}>{fmtScore(s.score)}/{s.total}</span>
                      )}
                      <span className="mono text-[10px] px-2 py-0.5 rounded shrink-0" style={{ background: `${st.color}18`, color: st.color }}>{st.label}</span>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}

          {/* Feedback preview */}
          {selected && selected.score !== null && (
            <Card className="p-5">
              <div className="flex items-center justify-between mb-4 gap-4">
                <div className="min-w-0">
                  <div className="text-sm truncate" style={{ color: 'var(--foreground)' }}>{selected.student}</div>
                  <div className="mono text-[11px]" style={{ color: 'var(--muted-foreground)' }}>AI Feedback Preview · confidence {selected.confidence ?? '—'}%{selected.model ? ` · ${selected.model}` : ''}</div>
                </div>
                <div className="text-2xl shrink-0" style={{ color: scoreColor(selected.score, selected.total) }}>{fmtScore(selected.score)}/{selected.total}</div>
              </div>
              {selected.flagReason && <Notice className="mb-3">⚠ {selected.flagReason}</Notice>}
              <div className="flex flex-col gap-3">
                {selected.criteria.map((c, i) => (
                  <div key={i} className="rounded p-3" style={{ background: 'var(--secondary)' }}>
                    <div className="flex items-center justify-between mb-1 gap-3">
                      <span className="text-xs" style={{ color: 'var(--foreground)' }}>{c.name}{c.level ? <span className="mono text-[10px] ml-2" style={{ color: 'var(--muted-foreground)' }}>{c.level}</span> : null}</span>
                      <span className="mono text-xs" style={{ color: c.earned === c.max ? '#22c55e' : 'var(--foreground)' }}>{fmtScore(c.earned)}/{c.max}</span>
                    </div>
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{c.note}</p>
                  </div>
                ))}
              </div>
              {selected.summary && <p className="text-xs leading-relaxed mt-3" style={{ color: 'var(--foreground)' }}>{selected.summary}</p>}
              {(role !== 'ta' || selected.status === 'review') && (
                <div className="mt-4 flex gap-2">
                  {selected.status !== 'graded' && (
                    <Button size="sm" onClick={async () => {
                      await saveSubmission({ ...selected, status: 'graded', approvedBy: me.id, approvedAt: Date.now(), flagReason: '' }).catch(() => undefined)
                      notify(`Grade approved for ${selected.student}.`)
                    }}>Approve Grade</Button>
                  )}
                  <Button size="sm" kind="secondary" onClick={() => setReviewId(selected.id)}>Edit Score</Button>
                </div>
              )}
            </Card>
          )}
        </div>

        {/* Right — config */}
        <div className="flex flex-col gap-4">
          <Card className="p-5">
            <Label className="mb-4">Rubric</Label>
            {sortedRubrics.length === 0 ? (
              <div className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>No rubrics yet. A professor or admin needs to add one before grading.</div>
            ) : (
              <div className="flex flex-col gap-2 max-h-72 overflow-y-auto" role="radiogroup" aria-label="Rubric">
                {sortedRubrics.map(r => (
                  <label
                    key={r.id}
                    className="flex items-start gap-3 p-3 rounded cursor-pointer transition-all"
                    style={{ background: rubricId === r.id ? 'rgba(59,111,255,0.08)' : 'var(--secondary)', border: `1px solid ${rubricId === r.id ? 'var(--primary)' : 'transparent'}` }}
                  >
                    <input type="radio" name="rubric" value={r.id} checked={rubricId === r.id} onChange={() => setRubricId(r.id)} className="mt-0.5 accent-[var(--primary)]" />
                    <div className="min-w-0">
                      <div className="text-xs" style={{ color: 'var(--foreground)' }}>{r.name}</div>
                      <div className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{r.criteria.length} criteria · {r.totalPoints} pts · {r.assignment}</div>
                    </div>
                  </label>
                ))}
              </div>
            )}
            <Button kind="dashed" size="sm" className="w-full mt-3" onClick={() => setActiveView('rubrics')}>+ Upload new rubric</Button>
          </Card>

          <Card className="p-5">
            <Label className="mb-4">Model</Label>
            <ModelBadge detailed />
          </Card>

          <Card className="p-5">
            <Label className="mb-3">Options</Label>
            <Checkbox id="opt-flag" checked={flagLow} onChange={setFlagLow} label={`Flag low-confidence grades for review (< ${settings.threshold}%)`} />
            <Checkbox id="opt-feedback" checked={detailed} onChange={setDetailed} label="Include per-criterion feedback" />
            <Checkbox id="opt-plag" checked={plagiarism} onChange={setPlagiarism} label="Detect plagiarism (pairwise)" />
          </Card>

          {uploading !== null ? (
            <Button size="lg" className="w-full" disabled><Spinner light /> Uploading… {uploading}%</Button>
          ) : pendingRows.length && !readyCount ? (
            <Button size="lg" className="w-full" onClick={stop}>
              <Spinner light /> {model.online ? 'Grading…' : 'Waiting for model…'} <span className="mono text-[11px] opacity-80">Stop</span>
            </Button>
          ) : (
            <Button size="lg" className="w-full" onClick={startGrading} disabled={reading || (!!staged.length && !rubric)}>
              {stage === 'done' && !readyCount ? '✓ Grading Complete' : <><StarIcon /> Start Grading{readyCount ? ` (${readyCount})` : ''}</>}
            </Button>
          )}

          {errorCount > 0 && !pendingRows.length && (
            <Button kind="secondary" size="sm" className="w-full" onClick={retryFailed}>Retry {errorCount} failed</Button>
          )}
          {readyCount > 0 && rubric && (
            <div className="mono text-[10px] text-center" style={{ color: 'var(--muted-foreground)' }}>
              {readyCount} file{readyCount === 1 ? '' : 's'} · {rubric.name}{model.waiting ? ` · ${model.waiting} already in queue` : ''}
            </div>
          )}
          {stage === 'done' && (doneCount + reviewCount) > 0 && (
            <Button kind="secondary" size="sm" className="w-full" onClick={() => setActiveView('submissions')}>Review in Submissions →</Button>
          )}
        </div>
      </div>

      <ReviewModal id={reviewId} onClose={() => setReviewId(null)} />
    </div>
  )
}
