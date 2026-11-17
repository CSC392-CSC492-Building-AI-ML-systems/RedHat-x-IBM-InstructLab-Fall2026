import { useEffect, useState } from 'react'
import { personName, useApp, usePeople, usePerms } from '../context'
import type { CriterionResult, Submission } from '../lib/types'
import { confColor, fmtScore, longDate, relTime, scoreColor } from '../lib/format'
import { Bar, Button, Confirm, Label, Modal, Notice, Spinner, StatusBadge } from './ui'

export default function ReviewModal({ id, onClose }: { id: string | null; onClose: () => void }) {
  const app = useApp()
  const { submissions, rubrics, me, saveSubmission, deleteSubmission, getContent, notify, logActivity, role, regrade: queueRegrade, model } = app
  const perms = usePerms()
  const sub = submissions.find(s => s.id === id) ?? null
  const [tab, setTab] = useState<'feedback' | 'file'>('feedback')
  const [draft, setDraft] = useState<Submission | null>(null)
  const [content, setContent] = useState<string | null>(null)
  const [busy, setBusy] = useState<'' | 'save' | 'regrade'>('')
  const [confirmDelete, setConfirmDelete] = useState(false)
  const people = usePeople(sub ? [sub.approvedBy ?? '', sub.uploadedBy, sub.gradedBy !== 'AI' ? sub.gradedBy : ''] : [])

  useEffect(() => {
    setDraft(sub ? structuredClone(sub) : null)
    setTab('feedback')
    setContent(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // keep draft in sync with live changes when the user hasn't edited
  useEffect(() => {
    if (sub && draft && sub.updatedAt !== draft.updatedAt && !dirty(sub, draft)) setDraft(structuredClone(sub))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sub?.updatedAt])

  useEffect(() => {
    if (tab === 'file' && content === null && id) getContent(id).then(setContent).catch(() => setContent(''))
  }, [tab, content, id, getContent])

  if (!id || !sub || !draft) return null

  const editable = perms.canApprove && (role !== 'ta' || sub.status !== 'graded' || !sub.approvedBy || sub.approvedBy === me.id)
  const rubric = rubrics.find(r => r.id === sub.rubricId)
  const draftScore = draft.criteria.length ? draft.criteria.reduce((a, c) => a + (Number(c.earned) || 0), 0) : draft.score
  const isDirty = dirty(sub, draft)

  function setCrit(i: number, p: Partial<CriterionResult>) {
    setDraft(d => d && ({ ...d, criteria: d.criteria.map((c, j) => (j === i ? { ...c, ...p } : c)) }))
  }

  async function save(approve: boolean) {
    if (!draft || !sub) return
    setBusy('save')
    try {
      const score = draft.criteria.length ? Math.round(draftScore! * 10) / 10 : draft.score
      const overridden = sub.aiScore !== null && score !== sub.aiScore
      const next: Submission = {
        ...draft,
        score,
        overridden: overridden || draft.overridden,
        gradedBy: overridden ? me.id : draft.gradedBy,
        status: approve ? 'graded' : draft.status,
        flagReason: approve ? '' : draft.flagReason,
        approvedBy: approve ? me.id : draft.approvedBy,
        approvedAt: approve ? Date.now() : draft.approvedAt,
      }
      await saveSubmission(next)
      if (overridden && score !== sub.score) {
        await logActivity('grade', 'Score overridden', `${sub.student} — ${sub.assignment}: ${fmtScore(sub.score)} → ${fmtScore(score)}/${sub.total}.`)
      }
      notify(approve ? `Grade approved for ${sub.student}.` : 'Changes saved.')
      if (approve) onClose()
    } catch { /* toast shown */ } finally {
      setBusy('')
    }
  }

  async function regrade() {
    if (!sub) return
    setBusy('regrade')
    try {
      await queueRegrade(sub.id)
      notify(model.online ? `${sub.student} is back in the queue — the model will regrade it now.` : `${sub.student} is queued. It will be regraded when the Fir model comes online.`)
      onClose()
    } catch { /* toast shown */ } finally {
      setBusy('')
    }
  }

  const input = 'w-full px-3 py-2 text-sm rounded outline-none'
  const inputStyle = { background: 'var(--muted)', color: 'var(--foreground)', border: '1px solid var(--border)' }

  return (
    <>
      <Modal
        open
        onClose={onClose}
        width={760}
        title={<span className="flex items-center gap-3">{sub.student} <StatusBadge status={sub.status} /></span>}
        sub={`${sub.file} · ${sub.assignment} · ${sub.rubricName}`}
        footer={
          <>
            {perms.canEditRubrics && <Button kind="danger" size="sm" className="mr-auto" onClick={() => setConfirmDelete(true)}>Delete</Button>}
            {sub.storedFile && (
              <a href={`/api/files/${encodeURIComponent(sub.id)}`} download={sub.file} className="px-3 py-1.5 text-xs rounded inline-flex items-center hover:opacity-80" style={{ background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }}>
                Download original
              </a>
            )}
            {editable && rubric && !(sub.status === 'pending' && sub.queueState === 'grading') && (
              <Button kind="secondary" size="sm" onClick={regrade} disabled={!!busy}>
                {busy === 'regrade' ? <><Spinner size={12} /> Queuing…</> : sub.status === 'pending' ? 'Queue again' : 'Regrade'}
              </Button>
            )}
            {editable && isDirty && <Button kind="secondary" size="sm" onClick={() => save(false)} disabled={!!busy}>Save changes</Button>}
            {editable && sub.status !== 'graded' && draft.criteria.length > 0 && (
              <Button size="sm" onClick={() => save(true)} disabled={!!busy}>{isDirty ? 'Save & approve' : 'Approve Grade'}</Button>
            )}
            {!editable && <Button kind="secondary" size="sm" onClick={onClose}>Close</Button>}
          </>
        }
      >
        {sub.flagReason && <Notice className="mb-4">⚠ {sub.flagReason}</Notice>}
        {sub.error && sub.status === 'pending' && <Notice kind="error" className="mb-4">{sub.error}</Notice>}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
          <div className="rounded p-3" style={{ background: 'var(--secondary)' }}>
            <Label className="mb-1">Score</Label>
            <div className="text-2xl" style={{ color: draftScore !== null ? scoreColor(draftScore, sub.total) : 'var(--muted-foreground)' }}>
              {fmtScore(draftScore)}<span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>/{sub.total}</span>
            </div>
            {sub.overridden && sub.aiScore !== null && <div className="mono text-[10px] mt-1" style={{ color: 'var(--muted-foreground)' }}>AI gave {fmtScore(sub.aiScore)}</div>}
          </div>
          <div className="rounded p-3" style={{ background: 'var(--secondary)' }}>
            <Label className="mb-2">AI Confidence</Label>
            {sub.confidence !== null ? (
              <div className="flex items-center gap-3">
                <Bar value={sub.confidence} color={confColor(sub.confidence)} height={6} />
                <span className="mono text-sm" style={{ color: confColor(sub.confidence) }}>{sub.confidence}%</span>
              </div>
            ) : <span className="mono text-xs" style={{ color: 'var(--muted-foreground)' }}>—</span>}
          </div>
          <div className="rounded p-3" style={{ background: 'var(--secondary)' }}>
            <Label className="mb-1">History</Label>
            <div className="mono text-[10px] leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              {sub.gradedAt ? `Graded ${relTime(sub.gradedAt)}` : `Uploaded ${longDate(sub.submittedAt)}`}
              {sub.approvedBy && <><br />Approved by {sub.approvedBy === me.id ? 'you' : personName(people, sub.approvedBy)}</>}
              {sub.overridden && sub.gradedBy !== 'AI' && <><br />Overridden by {sub.gradedBy === me.id ? 'you' : personName(people, sub.gradedBy)}</>}
            </div>
          </div>
        </div>

        <div className="flex gap-1 mb-4 border-b" style={{ borderColor: 'var(--border)' }} role="tablist">
          {(['feedback', 'file'] as const).map(t => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className="pb-2 px-3 text-xs"
              style={{ color: tab === t ? 'var(--primary)' : 'var(--muted-foreground)', borderBottom: tab === t ? '2px solid var(--primary)' : '2px solid transparent', marginBottom: -1 }}
            >
              {t === 'feedback' ? 'Feedback' : 'Submission'}
            </button>
          ))}
        </div>

        {tab === 'feedback' ? (
          <div className="flex flex-col gap-3">
            {draft.criteria.length === 0 && <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>This file hasn't been graded yet.</div>}
            {draft.criteria.map((c, i) => (
              <div key={i} className="rounded p-3" style={{ background: 'var(--secondary)' }}>
                <div className="flex items-center justify-between mb-2 gap-3">
                  <span className="text-xs" style={{ color: 'var(--foreground)' }}>
                    {c.name}{c.level ? <span className="mono text-[10px] ml-2" style={{ color: 'var(--muted-foreground)' }}>{c.level}</span> : null}
                  </span>
                  {editable ? (
                    <span className="flex items-center gap-1 mono text-xs">
                      <label className="sr-only" htmlFor={`crit-${i}`}>{c.name} points</label>
                      <input
                        id={`crit-${i}`}
                        type="number"
                        min={0}
                        max={c.max}
                        step={0.5}
                        value={c.earned}
                        onChange={e => setCrit(i, { earned: Math.max(0, Math.min(c.max, Number(e.target.value))) })}
                        className="w-14 px-2 py-1 rounded text-right outline-none"
                        style={inputStyle}
                      />
                      <span style={{ color: 'var(--muted-foreground)' }}>/{c.max}</span>
                    </span>
                  ) : (
                    <span className="mono text-xs" style={{ color: c.earned === c.max ? '#22c55e' : 'var(--foreground)' }}>{fmtScore(c.earned)}/{c.max}</span>
                  )}
                </div>
                {editable ? (
                  <textarea
                    aria-label={`${c.name} feedback`}
                    value={c.note}
                    rows={2}
                    onChange={e => setCrit(i, { note: e.target.value })}
                    className="w-full text-xs leading-relaxed rounded px-2 py-1.5 outline-none resize-y"
                    style={inputStyle}
                  />
                ) : (
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{c.note}</p>
                )}
              </div>
            ))}
            {(draft.summary || editable) && draft.criteria.length > 0 && (
              <div>
                <Label className="mb-1">Overall feedback</Label>
                {editable ? (
                  <textarea aria-label="Overall feedback" value={draft.summary} rows={3} onChange={e => setDraft({ ...draft, summary: e.target.value })} className="w-full text-xs leading-relaxed rounded px-3 py-2 outline-none resize-y" style={inputStyle} />
                ) : (
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--foreground)' }}>{draft.summary}</p>
                )}
              </div>
            )}
            {editable && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-2">
                <div>
                  <label htmlFor="rv-name" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Student</label>
                  <input id="rv-name" type="text" value={draft.student} onChange={e => setDraft({ ...draft, student: e.target.value })} className={input} style={inputStyle} />
                </div>
                <div>
                  <label htmlFor="rv-id" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Student ID</label>
                  <input id="rv-id" type="text" value={draft.studentId} onChange={e => setDraft({ ...draft, studentId: e.target.value })} className={input} style={inputStyle} />
                </div>
                <div>
                  <label htmlFor="rv-email" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Email</label>
                  <input id="rv-email" type="text" value={draft.email} onChange={e => setDraft({ ...draft, email: e.target.value })} className={input} style={inputStyle} />
                </div>
              </div>
            )}
          </div>
        ) : (
          <div>
            {content === null ? (
              <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--muted-foreground)' }}><Spinner size={12} /> Loading…</div>
            ) : content ? (
              <pre className="submission text-[11px] leading-relaxed whitespace-pre-wrap break-words rounded p-4 max-h-[420px] overflow-auto" style={{ background: 'var(--secondary)', color: 'var(--foreground)' }}>{content}</pre>
            ) : (
              <div className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
                {sub.queueState === 'ocr' ? 'The server is still reading this scan.' : 'No readable text was found in this file. Download the original to look at it.'}
              </div>
            )}
          </div>
        )}
      </Modal>
      <Confirm
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        danger
        title="Delete this submission?"
        body={`${sub.student}'s ${sub.file} and its grade will be removed for everyone. This can't be undone.`}
        confirmLabel="Delete submission"
        onConfirm={async () => { await deleteSubmission(sub.id).catch(() => undefined); notify('Submission deleted.'); onClose() }}
      />
    </>
  )
}

function dirty(a: Submission, b: Submission) {
  return a.student !== b.student || a.studentId !== b.studentId || a.email !== b.email || a.summary !== b.summary ||
    JSON.stringify(a.criteria.map(c => [c.earned, c.note])) !== JSON.stringify(b.criteria.map(c => [c.earned, c.note]))
}
