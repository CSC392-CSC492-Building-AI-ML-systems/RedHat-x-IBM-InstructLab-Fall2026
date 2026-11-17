import { useEffect, useMemo, useState } from 'react'
import { personName, useApp, usePeople, usePerms } from '../context'
import { confColor, fmtScore, longDate, scoreColor } from '../lib/format'
import type { Submission } from '../lib/types'
import { AssignmentPicker } from './assignments'
import { shortCourse } from './Sidebar'
import { Bar, Button, Card, Empty, Label, Notice, StatusBadge } from './ui'
import ReviewModal from './ReviewModal'

type Filter = 'all' | 'graded' | 'review' | 'pending'
const ORDER = { review: 0, pending: 1, error: 1, graded: 2 } as const

export default function Submissions({ focusId, clearFocus }: { focusId: string | null; clearFocus: () => void }) {
  const { submissions, settings, me, saveSubmission, notify, model } = useApp()
  const { canApprove } = usePerms()
  const [assignment, setAssignment] = useState(settings.currentAssignment)
  const [filter, setFilter] = useState<Filter>('all')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [reviewId, setReviewId] = useState<string | null>(null)
  const [limit, setLimit] = useState(100)

  useEffect(() => {
    if (!focusId) return
    const s = submissions.find(x => x.id === focusId)
    if (s) { setAssignment(s.assignment); setFilter('all'); setSelectedId(s.id) }
    clearFocus()
  }, [focusId, submissions, clearFocus])

  const inAssignment = useMemo(() => submissions.filter(s => s.assignment === assignment), [submissions, assignment])

  useEffect(() => {
    if (!selectedId && !focusId) setSelectedId(inAssignment.find(s => s.status === 'review')?.id ?? null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assignment])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return inAssignment
      .filter(s => {
        if (filter === 'pending' && !(s.status === 'pending' || s.status === 'error')) return false
        if (filter !== 'all' && filter !== 'pending' && s.status !== filter) return false
        if (q && !s.student.toLowerCase().includes(q) && !s.file.toLowerCase().includes(q) && !s.studentId.includes(q)) return false
        return true
      })
      .sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.student.localeCompare(b.student))
  }, [inAssignment, filter, search])

  const reviewCount = inAssignment.filter(s => s.status === 'review').length
  const selected = submissions.find(s => s.id === selectedId) ?? null
  const people = usePeople(filtered.slice(0, limit).flatMap(s => [s.gradedBy, s.approvedBy ?? '']).filter(x => x && x !== 'AI' && x !== '—'))

  const highConfidence = inAssignment.filter(s => s.status === 'review' && (s.confidence ?? 0) >= settings.threshold && !s.similarity && s.criteria.length)

  async function approve(s: Submission) {
    await saveSubmission({ ...s, status: 'graded', flagReason: '', approvedBy: me.id, approvedAt: Date.now() })
    notify(`Grade approved for ${s.student}.`)
  }

  async function approveAll() {
    for (const s of highConfidence) await saveSubmission({ ...s, status: 'graded', flagReason: '', approvedBy: me.id, approvedAt: Date.now() }).catch(() => undefined)
    notify(`${highConfidence.length} grades approved.`)
  }

  function byLabel(s: Submission) {
    if (s.status === 'pending' || s.status === 'error') return '—'
    if (s.overridden && s.gradedBy !== 'AI') return s.gradedBy === me.id ? 'You' : shortName(personName(people, s.gradedBy, 'TA'))
    return 'AI'
  }

  return (
    <div className="p-4 md:p-8 max-w-screen-xl mx-auto">
      <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mono text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted-foreground)' }}>{shortCourse(settings.code)} · {assignment}</div>
          <h1 className="text-2xl tracking-tight" style={{ color: 'var(--foreground)' }}>Submissions</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {canApprove && highConfidence.length > 0 && (
            <Button kind="secondary" size="sm" onClick={approveAll}>Approve {highConfidence.length} above {settings.threshold}% confidence</Button>
          )}
          <AssignmentPicker id="subs-assignment" value={assignment} onChange={a => { setAssignment(a); setSelectedId(null) }} />
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="flex rounded overflow-hidden" style={{ border: '1px solid var(--border)', background: 'var(--card)' }} role="tablist" aria-label="Filter by status">
          {(['all', 'graded', 'review', 'pending'] as Filter[]).map(f => (
            <button
              key={f}
              type="button"
              role="tab"
              aria-selected={filter === f}
              onClick={() => setFilter(f)}
              className="px-3 py-1.5 text-xs transition-all capitalize"
              style={{ background: filter === f ? 'var(--primary)' : 'transparent', color: filter === f ? '#fff' : 'var(--muted-foreground)' }}
            >
              {f}
              {f === 'review' && reviewCount > 0 && (
                <span className="ml-1 mono text-[10px] px-1 rounded" style={{ background: 'rgba(245,158,11,0.2)', color: filter === f ? '#fff' : '#d97706' }}>{reviewCount}</span>
              )}
            </button>
          ))}
        </div>
        <label htmlFor="sub-search" className="sr-only">Search</label>
        <input
          id="sub-search"
          type="search"
          placeholder="Search student, ID or file…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="px-3 py-1.5 text-sm rounded outline-none w-full sm:w-[240px]"
          style={{ background: 'var(--card)', color: 'var(--foreground)', border: '1px solid var(--border)' }}
        />
        <div className="ml-auto mono text-xs" style={{ color: 'var(--muted-foreground)' }}>{filtered.length} results</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 items-start">
        {/* Table */}
        <Card className="lg:col-span-3 overflow-hidden">
          {inAssignment.length === 0 ? (
            <Empty title={`No submissions for ${assignment}`} body="Graded files appear here as soon as a batch finishes. Everyone on the course team sees the same list." />
          ) : filtered.length === 0 ? (
            <Empty title="No matches" body="Try another filter or search." height={160} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[520px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Student', 'Score', 'Confidence', 'Status', 'By'].map(h => (
                      <th key={h} className="px-4 py-3 text-left mono text-[10px] uppercase tracking-widest font-normal" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.slice(0, limit).map((s, i, arr) => {
                    const isSel = s.id === selectedId
                    return (
                      <tr
                        key={s.id}
                        onClick={() => setSelectedId(isSel ? null : s.id)}
                        onKeyDown={e => { if (e.key === 'Enter') setSelectedId(isSel ? null : s.id) }}
                        tabIndex={0}
                        aria-selected={isSel}
                        className="cursor-pointer transition-colors hover:bg-[var(--secondary)]"
                        style={{
                          borderBottom: i < arr.length - 1 ? '1px solid var(--border)' : 'none',
                          background: isSel ? 'rgba(59,111,255,0.06)' : 'transparent',
                          boxShadow: isSel ? 'inset 2px 0 0 var(--primary)' : 'none',
                        }}
                      >
                        <td className="px-4 py-3 max-w-[220px]">
                          <div className="truncate" style={{ color: 'var(--foreground)' }}>{s.student}</div>
                          <div className="mono text-[10px] truncate" style={{ color: 'var(--muted-foreground)' }}>{s.studentId || s.file}</div>
                        </td>
                        <td className="px-4 py-3 mono text-xs" style={{ color: s.score !== null ? scoreColor(s.score, s.total) : 'var(--muted-foreground)' }}>
                          {s.score !== null ? `${fmtScore(s.score)}/${s.total}` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          {s.confidence !== null ? (
                            <div className="flex items-center gap-2">
                              <div className="w-12"><Bar value={s.confidence} color={confColor(s.confidence)} /></div>
                              <span className="mono text-[10px]" style={{ color: confColor(s.confidence) }}>{s.confidence}%</span>
                            </div>
                          ) : <span className="mono text-xs" style={{ color: 'var(--muted-foreground)' }}>—</span>}
                        </td>
                        <td className="px-4 py-3">
                          {s.status === 'pending' && s.queueState
                            ? <span className="mono text-[10px] px-2 py-0.5 rounded whitespace-nowrap" style={{ background: 'rgba(107,114,145,0.12)', color: 'var(--muted-foreground)' }}>{s.queueState === 'grading' ? 'Grading…' : s.queueState === 'ocr' ? 'OCR…' : model.online ? 'Queued' : 'Waiting'}</span>
                            : <StatusBadge status={s.status} short />}
                        </td>
                        <td className="px-4 py-3 mono text-xs" style={{ color: 'var(--muted-foreground)' }}>{byLabel(s)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {filtered.length > limit && (
                <div className="p-3 text-center border-t" style={{ borderColor: 'var(--border)' }}>
                  <Button kind="ghost" size="sm" onClick={() => setLimit(l => l + 100)}>Show {Math.min(100, filtered.length - limit)} more</Button>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Detail */}
        <div className="lg:col-span-2">
          {selected ? (
            <Card className="lg:sticky lg:top-4">
              <div className="px-5 py-4 border-b flex items-start justify-between gap-3" style={{ borderColor: 'var(--border)' }}>
                <div className="min-w-0">
                  <div className="text-sm truncate" style={{ color: 'var(--foreground)' }}>{selected.student}</div>
                  <div className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{selected.studentId || 'No student ID'} · {selected.assignment}</div>
                </div>
                {selected.score !== null && (
                  <div className="text-xl shrink-0" style={{ color: scoreColor(selected.score, selected.total) }}>{fmtScore(selected.score)}/{selected.total}</div>
                )}
              </div>

              {selected.flagReason && <Notice className="mx-4 mt-4">⚠ {selected.flagReason}</Notice>}
              {selected.error && selected.status === 'pending' && <Notice kind="error" className="mx-4 mt-4">{selected.error}</Notice>}

              <div className="p-4 flex flex-col gap-3">
                <div className="rounded p-3" style={{ background: 'var(--secondary)' }}>
                  <Label className="mb-2">File</Label>
                  <div className="mono text-xs break-all" style={{ color: 'var(--foreground)' }}>{selected.file}</div>
                  <div className="mono text-[10px] mt-0.5" style={{ color: 'var(--muted-foreground)' }}>Uploaded {longDate(selected.submittedAt)} · {selected.rubricName}{selected.model ? ` · graded by ${selected.model}` : ''}</div>
                  {selected.status === 'pending' && (
                    <div className="mono text-[10px] mt-1" style={{ color: 'var(--primary)' }}>
                      {selected.queueState === 'grading' ? 'Being graded now' : selected.queueState === 'ocr' ? 'Reading the scan on the server' : model.online ? 'In the queue' : 'Waiting for the Fir model to come online'}
                    </div>
                  )}
                </div>

                {selected.confidence !== null && (
                  <div className="rounded p-3" style={{ background: 'var(--secondary)' }}>
                    <Label className="mb-2">AI Confidence</Label>
                    <div className="flex items-center gap-3">
                      <Bar value={selected.confidence} color={confColor(selected.confidence)} height={8} />
                      <span className="mono text-sm" style={{ color: confColor(selected.confidence) }}>{selected.confidence}%</span>
                    </div>
                  </div>
                )}

                {selected.summary && (
                  <div className="rounded p-3" style={{ background: 'var(--secondary)' }}>
                    <Label className="mb-2">Summary</Label>
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--foreground)' }}>{selected.summary}</p>
                  </div>
                )}

                <div className="flex flex-col gap-2 mt-1">
                  {selected.status === 'review' && canApprove && (
                    <>
                      <Button className="w-full" onClick={() => approve(selected)}>Approve Grade</Button>
                      <Button kind="secondary" className="w-full" onClick={() => setReviewId(selected.id)}>Override Score</Button>
                    </>
                  )}
                  <Button kind="secondary" className="w-full" onClick={() => setReviewId(selected.id)}>
                    {selected.status === 'pending' ? 'Open File' : 'View Full Feedback'}
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="flex items-center justify-center" style={{ height: 200 }}>
              <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>Select a submission to review</span>
            </Card>
          )}
        </div>
      </div>

      <ReviewModal id={reviewId} onClose={() => setReviewId(null)} />
    </div>
  )
}

function shortName(n: string) {
  const parts = n.replace(/^(Prof\.?|Dr\.?)\s+/i, '').split(' ')
  return parts.length > 1 ? `${parts[0]} ${parts[parts.length - 1][0]}.` : n
}
