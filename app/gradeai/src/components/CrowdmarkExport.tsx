import { useMemo, useState } from 'react'
import { personName, useApp, usePeople, usePerms } from '../context'
import { formatBytes } from '../lib/files'
import { longDate, relTime, slug, toCSV } from '../lib/format'
import { matchRoster } from '../lib/grading'
import type { Submission } from '../lib/types'
import { useAssignments } from './assignments'
import { Button, Card, Checkbox, Label, Notice, SendIconWhite, Spinner } from './ui'

type Status = 'idle' | 'exporting' | 'done' | 'error'
interface LogLine { time: string; message: string; type: 'ok' | 'warn' | 'info' | 'error' }

const LOG_COLOR: Record<LogLine['type'], string> = { ok: '#16a34a', warn: '#d97706', info: 'var(--muted-foreground)', error: '#ef4444' }

export default function CrowdmarkExport() {
  const { settings, submissions, exports, me, download, addExport, logActivity, notify } = useApp()
  const { canExport } = usePerms()
  const assignments = useAssignments()
  const [selected, setSelected] = useState(settings.currentAssignment)
  const [includeComments, setIncludeComments] = useState(true)
  const [includeReview, setIncludeReview] = useState(false)
  const [status, setStatus] = useState<Status>('idle')
  const [log, setLog] = useState<LogLine[]>([])
  const [progress, setProgress] = useState(0)
  const [lastCsv, setLastCsv] = useState<{ name: string; data: string } | null>(null)
  const people = usePeople(exports.map(e => e.by))

  const perAssignment = useMemo(() => assignments.map(a => {
    const subs = submissions.filter(s => s.assignment === a)
    const graded = subs.filter(s => s.status === 'graded').length
    const last = exports.find(e => e.assignment === a)
    return { name: a, graded, total: Math.max(subs.length, a === settings.currentAssignment ? settings.enrollment : subs.length), uploaded: subs.length, last }
  }), [assignments, submissions, exports, settings.currentAssignment, settings.enrollment])

  const plan = useMemo(() => {
    const subs = submissions.filter(s => s.assignment === selected)
    const eligible = (s: Submission) => {
      if (s.score === null) return false
      if (s.status === 'graded') return settings.requireSignoff ? !!s.approvedBy : true
      return includeReview && s.status === 'review'
    }
    const included = subs.filter(eligible)
    return { subs, included, excluded: subs.length - included.length }
  }, [submissions, selected, includeReview, settings.requireSignoff])

  async function startExport() {
    if (!canExport || status === 'exporting') return
    setStatus('exporting')
    setLog([])
    setProgress(0)
    setLastCsv(null)
    const lines: LogLine[] = []
    const push = async (message: string, type: LogLine['type'], pct: number) => {
      lines.push({ time: new Date().toLocaleTimeString([], { hour12: false }), message, type })
      setLog([...lines])
      setProgress(pct)
      await new Promise(r => setTimeout(r, 160))
    }

    try {
      const { subs, included, excluded } = plan
      await push(`Collecting grades — ${settings.code} · ${selected}`, 'ok', 8)
      await push(`${subs.length} submission${subs.length === 1 ? '' : 's'} on file, ${included.length} eligible for export`, 'ok', 18)
      if (!included.length) {
        await push('Nothing to export. Finalize some grades first.', 'error', 100)
        setStatus('error')
        return
      }
      if (excluded) await push(`${excluded} submission${excluded === 1 ? '' : 's'} ${settings.requireSignoff ? 'pending or without TA sign-off' : 'pending or in review'} — excluded from export`, 'warn', 28)

      // roster matching
      let matched = 0
      const rows = included.map(s => {
        const r = matchRoster(settings.roster, { studentId: s.studentId, name: s.student, fileName: s.file })
        if (r) matched++
        return { s, name: r?.name ?? s.student, email: r?.email || s.email, id: r?.studentId || s.studentId }
      })
      if (settings.roster.length) await push(`Matched ${matched} of ${included.length} to the class roster (${settings.roster.length} students)`, matched === included.length ? 'ok' : 'warn', 42)
      else await push('No class roster uploaded — names and IDs come from the submissions (add one in Settings)', 'warn', 42)
      const missing = rows.filter(r => !r.id && !r.email).length
      if (missing) await push(`${missing} row${missing === 1 ? '' : 's'} have no student ID or email — fill these in before uploading`, 'warn', 50)

      // columns: one per question (criterion), like Crowdmark's own grade export
      const critNames: string[] = []
      for (const r of rows) for (const c of r.s.criteria) if (!critNames.includes(c.name)) critNames.push(c.name)
      const outOf = Math.max(...rows.map(r => r.s.total))
      const header = ['Name', 'Email', 'Student ID', ...critNames, 'Total', 'Out of', ...(includeComments ? ['Feedback'] : [])]
      await push(`Building CSV: ${header.length} columns (${critNames.length} criteria${includeComments ? ' + feedback' : ''})`, 'info', 62)
      const body = rows
        .sort((a, b) => a.name.localeCompare(b.name))
        .map(({ s, name, email, id }) => {
          const byName = new Map(s.criteria.map(c => [c.name, c.earned]))
          const feedback = includeComments
            ? [s.summary, ...s.criteria.filter(c => c.note).map(c => `${c.name} (${c.earned}/${c.max}): ${c.note}`)].filter(Boolean).join('\n')
            : null
          return [name, email, id, ...critNames.map(n => byName.get(n) ?? ''), s.score, s.total, ...(includeComments ? [feedback] : [])]
        })
      const csv = '﻿' + toCSV([header, ...body])
      const filename = `${slug(settings.code)}-${slug(selected)}-grades-${localDate()}.csv`
      await push(`Wrote ${filename} · ${rows.length} rows · ${formatBytes(new Blob([csv]).size)} · out of ${outOf}`, 'ok', 76)
      setLastCsv({ name: filename, data: csv })

      download(filename, csv)
      await push(`Downloaded ${filename}`, 'ok', 92)

      await addExport({ assignment: selected, count: rows.length, excluded, at: Date.now(), by: me.id, filename })
      await logActivity('export', 'Crowdmark export ready', `${selected} — ${rows.length} grades exported${includeComments ? ' with feedback comments' : ''}.`)
      await push('Export complete. Upload the file to Crowdmark (or your LMS gradebook) to release grades.', 'ok', 100)
      setStatus('done')
    } catch {
      await push('Export failed. Check your connection and try again.', 'error', 100)
      setStatus('error')
    }
  }

  async function copyCsv() {
    if (!lastCsv) return
    try { await navigator.clipboard.writeText(lastCsv.data.replace(/^﻿/, '')); notify('CSV copied — paste it into a spreadsheet and save as .csv.') }
    catch { notify('Could not copy to the clipboard.', 'error') }
  }

  const active = status === 'exporting'

  return (
    <div className="p-4 md:p-8 max-w-screen-xl mx-auto">
      <div className="mb-8">
        <div className="mono text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted-foreground)' }}>Crowdmark Integration</div>
        <h1 className="text-2xl tracking-tight" style={{ color: 'var(--foreground)' }}>Export to Crowdmark</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>
          Package finalized grades and AI-generated feedback in Crowdmark's grade-file layout.
        </p>
      </div>

      {!canExport && (
        <Notice className="mb-6 text-sm">Crowdmark export requires Professor or Administrator role. Contact {settings.instructor} to initiate export.</Notice>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="flex flex-col gap-4">
          <Card className="p-5">
            <Label className="mb-3">Connection</Label>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: '#22c55e' }} />
              <div className="min-w-0">
                <div className="text-sm" style={{ color: 'var(--foreground)' }}>Crowdmark grade file</div>
                <div className="mono text-[10px] truncate" style={{ color: 'var(--muted-foreground)' }}>{settings.crowdmarkCourse} · {settings.institution}</div>
              </div>
            </div>
            <div className="mono text-[10px] px-2 py-1.5 rounded leading-relaxed" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>
              Name · Email · Student ID · one column per question · Total
            </div>
          </Card>

          <Card className="p-5">
            <Label className="mb-3">Assignment</Label>
            <div className="flex flex-col gap-2" role="radiogroup" aria-label="Assignment">
              {perAssignment.map(a => (
                <label
                  key={a.name}
                  className="rounded p-3 flex items-start gap-3 cursor-pointer transition-all"
                  style={{ background: selected === a.name ? 'rgba(59,111,255,0.08)' : 'var(--secondary)', border: `1px solid ${selected === a.name ? 'var(--primary)' : 'transparent'}` }}
                >
                  <input type="radio" name="assignment" checked={selected === a.name} onChange={() => setSelected(a.name)} disabled={active} className="mt-0.5 accent-[var(--primary)]" />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
                      {a.name}
                      {a.last && <span className="mono text-[9px] px-1.5 rounded" style={{ background: 'rgba(34,197,94,0.12)', color: '#16a34a' }}>Exported</span>}
                    </div>
                    <div className="mono text-[10px] mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                      {a.graded}/{a.total} graded{a.last ? ` · ${longDate(a.last.at)}` : ''}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <Label className="mb-3">Options</Label>
            <Checkbox id="cm-comments" checked={includeComments} onChange={setIncludeComments} disabled={active} label="Include AI feedback comments" />
            <Checkbox id="cm-review" checked={includeReview} onChange={setIncludeReview} disabled={active} label="Include grades still in review" />
          </Card>

          <div className="rounded p-4" style={{ background: 'var(--secondary)', border: '1px solid var(--border)' }}>
            <Label className="mb-2">Export Summary</Label>
            <Row label="Grades to export" value={String(plan.included.length)} />
            <Row label={settings.requireSignoff ? 'Excluded (pending / no sign-off)' : 'Excluded (pending)'} value={String(plan.excluded)} color="#d97706" />
            <Row label="Feedback comments" value={includeComments ? 'Yes' : 'No'} />
            <Row label="Class roster" value={settings.roster.length ? `${settings.roster.length} students` : 'Not uploaded'} />
          </div>

          <Button
            size="lg"
            className="w-full"
            onClick={startExport}
            disabled={!canExport || active}
            style={!canExport ? { background: 'var(--secondary)', color: 'var(--muted-foreground)' } : undefined}
          >
            {active ? <><Spinner light /> Exporting…</> : status === 'done' ? '✓ Export Complete' : <><SendIconWhite /> Export for Crowdmark</>}
          </Button>
        </div>

        {/* Log */}
        <Card className="lg:col-span-2 overflow-hidden flex flex-col">
          <div className="px-5 py-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <span className="text-sm" style={{ color: 'var(--foreground)' }}>Export Log</span>
            {active && (
              <div className="flex items-center gap-2">
                <div className="w-24 h-1 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${progress}%`, background: 'var(--primary)' }} />
                </div>
                <span className="mono text-[11px]" style={{ color: 'var(--primary)' }}>{progress}%</span>
              </div>
            )}
            {status === 'done' && <span className="mono text-[11px]" style={{ color: '#16a34a' }}>✓ Complete</span>}
          </div>

          <div className="p-4 mono text-xs flex-1" style={{ minHeight: 360 }} aria-live="polite">
            {log.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-64 text-center" style={{ color: 'var(--muted-foreground)' }}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" className="mb-3 opacity-30" aria-hidden>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="1.5" />
                  <polyline points="14 2 14 8 20 8" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" strokeWidth="1.5" />
                  <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" strokeWidth="1.5" />
                </svg>
                <span>Export log will appear here</span>
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                {log.map((l, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="shrink-0" style={{ color: 'var(--muted-foreground)' }}>{l.time}</span>
                    <span style={{ color: LOG_COLOR[l.type] }}>{l.type === 'ok' ? '✓' : l.type === 'warn' ? '⚠' : l.type === 'error' ? '✗' : '·'}</span>
                    <span className="break-words min-w-0" style={{ color: l.type === 'info' ? 'var(--foreground)' : LOG_COLOR[l.type] }}>{l.message}</span>
                  </div>
                ))}
                {active && (
                  <div className="flex gap-3"><span style={{ color: 'var(--muted-foreground)' }}>…</span><span className="animate-pulse" style={{ color: 'var(--primary)' }}>█</span></div>
                )}
              </div>
            )}
          </div>

          {status === 'done' && lastCsv && (
            <div className="px-4 pb-4 border-t pt-4 flex flex-col gap-3" style={{ borderColor: 'var(--border)' }}>
              <div className="rounded px-4 py-3 text-sm flex items-center gap-3" style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', color: '#15803d' }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
                  <circle cx="8" cy="8" r="7" stroke="#16a34a" strokeWidth="1.5" />
                  <path d="M5 8l2 2 4-4" stroke="#16a34a" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span className="flex-1">{plan.included.length} grades packaged in {lastCsv.name}.</span>
                <Button kind="secondary" size="sm" onClick={() => download(lastCsv.name, lastCsv.data)}>Download again</Button>
                <Button kind="secondary" size="sm" onClick={copyCsv}>Copy CSV</Button>
              </div>
            </div>
          )}

          {exports.length > 0 && (
            <div className="border-t" style={{ borderColor: 'var(--border)' }}>
              <div className="px-5 pt-4 pb-2"><Label>Export history</Label></div>
              {exports.slice(0, 6).map(e => (
                <div key={e.id} className="px-5 py-2 flex items-center gap-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                  <span style={{ color: 'var(--foreground)' }}>{e.assignment}</span>
                  <span className="mono">{e.count} grades</span>
                  <span className="mono truncate flex-1 min-w-0">{e.filename}</span>
                  <span className="mono shrink-0">{relTime(e.at)} · {e.by === me.id ? 'you' : personName(people, e.by)}</span>
                </div>
              ))}
              <div className="h-3" />
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex justify-between text-xs mb-1 gap-3">
      <span style={{ color: 'var(--muted-foreground)' }}>{label}</span>
      <span className="mono" style={{ color: color ?? 'var(--foreground)' }}>{value}</span>
    </div>
  )
}

function localDate(d = new Date()) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}
