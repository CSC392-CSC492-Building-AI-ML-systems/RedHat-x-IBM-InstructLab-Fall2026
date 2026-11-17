import { useMemo, useState } from 'react'
import type { View } from '../lib/types'
import { useApp, usePerms } from '../context'
import { fmtScore, greeting, relTime, scoreColor } from '../lib/format'
import { Button, Card, Empty, StarIcon, StatusBadge } from './ui'
import { AssignmentPicker, useAssignments } from './assignments'
import { shortCourse } from './Sidebar'

interface Props {
  setActiveView: (v: View) => void
  openSubmission: (id: string) => void
}

export default function Dashboard({ setActiveView, openSubmission }: Props) {
  const { me, settings, submissions } = useApp()
  const { canExport } = usePerms()
  const assignments = useAssignments()
  const [assignment, setAssignment] = useState(settings.currentAssignment)

  const stats = useMemo(() => {
    const subs = submissions.filter(s => s.assignment === assignment)
    const graded = subs.filter(s => s.status === 'graded')
    const review = subs.filter(s => s.status === 'review')
    const waiting = subs.filter(s => s.status === 'pending' || s.status === 'error')
    const scored = subs.filter(s => s.score !== null && s.total > 0)
    const weekAgo = Date.now() - 7 * 864e5
    const thisWeek = graded.filter(s => (s.approvedAt ?? s.gradedAt ?? 0) > weekAgo).length
    const avg = scored.length ? (scored.reduce((a, s) => a + (s.score! / s.total), 0) / scored.length) * 100 : null

    // compare with the assignment graded most recently before this one
    const others = assignments.filter(a => a !== assignment)
    let prevAvg: number | null = null
    let prevName = ''
    for (const a of others) {
      const ps = submissions.filter(s => s.assignment === a && s.score !== null && s.total > 0)
      if (ps.length) { prevAvg = (ps.reduce((x, s) => x + s.score! / s.total, 0) / ps.length) * 100; prevName = a; break }
    }
    const aiGraded = subs.filter(s => s.aiScore !== null).length
    const hours = (aiGraded * settings.minutesPerManualGrade) / 60
    const autoGraded = graded.filter(s => !s.approvedBy && !s.overridden).length
    const taReviewed = graded.length - autoGraded
    const denom = Math.max(settings.enrollment || 0, subs.length)
    const flagged = review.filter(s => s.flagReason).length
    return { subs, graded, review, waiting, thisWeek, avg, prevAvg, prevName, hours, autoGraded, taReviewed, denom, flagged, aiGraded, scoredCount: scored.length }
  }, [submissions, assignment, assignments, settings.enrollment, settings.minutesPerManualGrade])

  const recent = useMemo(
    () => submissions.filter(s => s.assignment === assignment).sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 6),
    [submissions, assignment],
  )

  const firstName = (me.name || 'there').replace(/^(Prof\.?|Dr\.?)\s+/i, '').split(' ')[0]
  const pendingCount = stats.review.length + stats.waiting.length
  const remaining = Math.max(0, stats.denom - stats.graded.length)

  const statusLine = stats.subs.length === 0
    ? `No submissions for ${assignment} yet. Start a batch to begin grading.`
    : remaining === 0
      ? `${assignment} grading is complete — ${stats.graded.length} of ${stats.denom} finalized.`
      : `${assignment} grading is in progress — ${stats.graded.length} of ${stats.denom} complete.`

  const deltaAvg = stats.avg !== null && stats.prevAvg !== null ? stats.avg - stats.prevAvg : null

  const STATS = [
    { label: 'Submissions Graded', value: String(stats.graded.length), delta: stats.thisWeek ? `+${stats.thisWeek} this week` : 'None finalized this week', color: 'var(--primary)' },
    { label: 'Pending Review', value: String(pendingCount), delta: `${stats.flagged} flagged by AI`, color: '#f59e0b' },
    {
      label: 'Avg Score',
      value: stats.avg === null ? '—' : `${stats.avg.toFixed(1)}%`,
      delta: deltaAvg !== null ? `${deltaAvg >= 0 ? '+' : ''}${deltaAvg.toFixed(1)}% vs ${shortAssignment(stats.prevName)}` : `Across ${stats.scoredCount} scored`,
      color: '#22c55e',
    },
    { label: 'Time Saved', value: `${stats.hours.toFixed(1)}h`, delta: `Est. at ${settings.minutesPerManualGrade} min per grade`, color: 'var(--accent)' },
  ]

  return (
    <div className="p-4 md:p-8 max-w-screen-xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mono text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted-foreground)' }}>
            {shortCourse(settings.code)} · {settings.name}
          </div>
          <h1 className="text-2xl tracking-tight" style={{ color: 'var(--foreground)' }}>
            {greeting()}, {firstName}
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>{statusLine}</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <AssignmentPicker value={assignment} onChange={setAssignment} id="dash-assignment" />
          <Button onClick={() => setActiveView('grade')}>
            <StarIcon /> Grade Batch
          </Button>
          {canExport && (
            <Button kind="secondary" onClick={() => setActiveView('crowdmark')}>Export to Crowdmark</Button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {STATS.map(s => (
          <Card key={s.label} className="p-5">
            <div className="text-[11px] uppercase tracking-wider mb-3" style={{ color: 'var(--primary)', opacity: 0.7 }}>{s.label}</div>
            <div className="text-3xl tracking-tight mono" style={{ color: s.color, fontFamily: 'Lexend, system-ui, sans-serif' }}>{s.value}</div>
            <div className="text-xs mt-1" style={{ color: 'var(--muted-foreground)' }}>{s.delta}</div>
          </Card>
        ))}
      </div>

      {/* Progress */}
      <Card className="p-4 mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:gap-6">
        <div className="flex-1">
          <div className="flex justify-between items-baseline mb-2 gap-3">
            <span className="text-sm" style={{ color: 'var(--foreground)' }}>{assignment} — Overall Progress</span>
            <span className="mono text-xs" style={{ color: 'var(--primary)' }}>{stats.graded.length} / {stats.denom}</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--secondary)' }} role="progressbar" aria-valuemin={0} aria-valuemax={stats.denom} aria-valuenow={stats.graded.length}>
            <div className="h-full rounded-full transition-all" style={{ width: `${stats.denom ? (stats.graded.length / stats.denom) * 100 : 0}%`, background: 'var(--primary)' }} />
          </div>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs" style={{ color: 'var(--muted-foreground)' }}>
          <div><span style={{ color: '#22c55e' }}>{stats.autoGraded}</span> auto-graded</div>
          <div><span style={{ color: '#f59e0b' }}>{stats.taReviewed}</span> TA reviewed</div>
          <div><span style={{ color: 'var(--muted-foreground)' }}>{remaining}</span> pending</div>
        </div>
      </Card>

      {/* Recent submissions */}
      <Card className="overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between border-b" style={{ borderColor: 'var(--border)' }}>
          <span className="text-sm" style={{ color: 'var(--foreground)' }}>Recent Submissions</span>
          <button type="button" onClick={() => setActiveView('submissions')} className="mono text-[11px] hover:opacity-70 transition-opacity" style={{ color: 'var(--primary)' }}>
            View all →
          </button>
        </div>
        {recent.length === 0 ? (
          <Empty
            title="No submissions yet"
            body={`Upload student files on Grade Batch and the model will grade them against your ${assignment} rubric.`}
            action={<Button size="sm" onClick={() => setActiveView('grade')}><StarIcon size={12} /> Start a batch</Button>}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[560px]">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Student', 'File', 'Score', 'Status', 'Time'].map(h => (
                    <th key={h} className="px-5 py-2.5 text-left mono text-[10px] uppercase tracking-widest font-normal" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recent.map((r, i) => (
                  <tr
                    key={r.id}
                    onClick={() => openSubmission(r.id)}
                    onKeyDown={e => { if (e.key === 'Enter') openSubmission(r.id) }}
                    tabIndex={0}
                    className="transition-colors hover:bg-[var(--secondary)] cursor-pointer"
                    style={{ borderBottom: i < recent.length - 1 ? '1px solid var(--border)' : 'none' }}
                  >
                    <td className="px-5 py-3" style={{ color: 'var(--foreground)' }}>{r.student}</td>
                    <td className="px-5 py-3 mono text-xs max-w-[200px] truncate" style={{ color: 'var(--muted-foreground)' }}>{r.file}</td>
                    <td className="px-5 py-3">
                      {r.score !== null ? (
                        <span className="mono text-xs" style={{ color: scoreColor(r.score, r.total) }}>{fmtScore(r.score)}/{r.total}</span>
                      ) : (
                        <span className="mono text-xs" style={{ color: 'var(--muted-foreground)' }}>—</span>
                      )}
                    </td>
                    <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-5 py-3 mono text-xs" style={{ color: 'var(--muted-foreground)' }}>{r.status === 'pending' ? 'queued' : relTime(r.updatedAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

function shortAssignment(a: string) {
  const m = a.match(/(\d+)/)
  return /assignment/i.test(a) && m ? `A${m[1]}` : a
}
