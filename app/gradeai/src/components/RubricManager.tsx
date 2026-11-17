import { useEffect, useRef, useState } from 'react'
import { personName, useApp, usePeople, usePerms } from '../context'
import type { Criterion, Rubric } from '../lib/types'
import { longDate, slug } from '../lib/format'
import { newId } from '../lib/store'
import { readText } from '../lib/files'
import { coerceRubric } from '../lib/grading'
import { ApiError } from '../lib/api'
import { Button, Card, Confirm, Empty, Notice, PageHeader, Spinner, UploadIcon } from './ui'

function bump(v: string) {
  const m = v.match(/^v?(\d+)\.(\d+)$/)
  return m ? `v${m[1]}.${Number(m[2]) + 1}` : 'v1.1'
}

function blankCriterion(): Criterion {
  return {
    name: 'New criterion', points: 10, description: '',
    levels: [
      { label: 'Full', points: 10, description: '' },
      { label: 'Partial', points: 5, description: '' },
      { label: 'None', points: 0, description: '' },
    ],
  }
}

function looksLikeId(s: string) { return /^(u_|local-)/.test(s) }

export default function RubricManager() {
  const { rubrics, settings, me, saveRubric, deleteRubric, logActivity, notify, importRubric, download, model } = useApp()
  const { canEditRubrics } = usePerms()
  const [selectedId, setSelectedId] = useState<string | null>(rubrics[0]?.id ?? null)
  const [expanded, setExpanded] = useState<number | null>(0)
  const [draft, setDraft] = useState<Rubric | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [importing, setImporting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!selectedId || !rubrics.find(r => r.id === selectedId)) setSelectedId(rubrics[0]?.id ?? null)
  }, [rubrics, selectedId])

  const selected = rubrics.find(r => r.id === selectedId) ?? null
  const shown = draft ?? selected
  const people = usePeople(rubrics.flatMap(r => [r.createdBy]).filter(looksLikeId))
  const author = (r: Rubric) => (looksLikeId(r.createdBy) ? (r.createdBy === me.id ? me.name : personName(people, r.createdBy)) : r.createdBy)

  function startNew() {
    setDraft({
      id: newId('r'), name: `${settings.currentAssignment.replace(/^Assignment\s*/i, 'A')} — New rubric`, assignment: settings.currentAssignment,
      version: 'v1.0', createdBy: me.id, updatedAt: Date.now(), totalPoints: 10, criteria: [blankCriterion()], instructions: '',
    })
    setIsNew(true)
    setExpanded(0)
  }

  function startEdit(focus?: number) {
    if (!selected) return
    setDraft(structuredClone(selected))
    setIsNew(false)
    if (focus !== undefined) setExpanded(focus)
  }

  async function save() {
    if (!draft) return
    const name = draft.name.trim()
    if (!name) { notify('Give the rubric a name.', 'warn'); return }
    if (!draft.criteria.length) { notify('Add at least one criterion.', 'warn'); return }
    const total = draft.criteria.reduce((a, c) => a + (Number(c.points) || 0), 0)
    const next: Rubric = { ...draft, name, totalPoints: total, version: isNew ? draft.version : bump(draft.version), updatedAt: Date.now() }
    try {
      await saveRubric(next)
      await logActivity('rubric', isNew ? 'Rubric created' : 'Rubric updated', `${next.name} (${next.version}, ${next.totalPoints} pts) for ${next.assignment}.${isNew ? '' : ' Review before the next batch.'}`)
      notify(isNew ? 'Rubric created.' : `Saved ${next.version}.`)
      setSelectedId(next.id)
      setDraft(null)
      setIsNew(false)
    } catch { /* toast shown */ }
  }

  async function duplicate() {
    if (!selected) return
    const copy: Rubric = { ...structuredClone(selected), id: newId('r'), name: `${selected.name} (copy)`, version: 'v1.0', createdBy: me.id, updatedAt: Date.now() }
    try {
      await saveRubric(copy)
      setSelectedId(copy.id)
      notify('Rubric duplicated.')
    } catch { /* toast shown */ }
  }

  async function remove() {
    if (!selected) return
    try {
      await deleteRubric(selected.id)
      await logActivity('rubric', 'Rubric deleted', `${selected.name} was removed from the library.`)
      notify('Rubric deleted.')
    } catch { /* toast shown */ }
  }

  async function exportJson() {
    if (!selected) return
    const { id: _id, ...rest } = selected
    void _id
    download(`${slug(selected.name)}.json`, JSON.stringify(rest, null, 2), 'application/json')
  }

  async function importFile(f: File | undefined) {
    if (!f) return
    setImporting(true)
    try {
      const text = await readText(f)
      let r: ReturnType<typeof coerceRubric>
      if (/\.json$/i.test(f.name)) {
        r = coerceRubric(JSON.parse(text), settings.currentAssignment)
      } else {
        if (!model.online) { notify('Reading a PDF or Word rubric needs the grading model, which is offline. Start the Fir job, or upload a .json rubric.', 'warn'); return }
        if (!text.trim()) { notify('No text found in that file. Is it a scan?', 'warn'); return }
        r = await importRubric(text, settings.currentAssignment)
      }
      if (!r.criteria.length) { notify('No criteria found in that file.', 'warn'); return }
      setDraft({ ...r, id: newId('r'), version: 'v1.0', createdBy: me.id, updatedAt: Date.now() })
      setIsNew(true)
      setExpanded(0)
      notify('Rubric read. Check it, then save.')
    } catch (e) {
      notify(e instanceof ApiError ? e.message : e instanceof SyntaxError ? 'That JSON file is not valid.' : 'Could not read that rubric file.', 'error')
    } finally {
      setImporting(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const setCrit = (i: number, p: Partial<Criterion>) => setDraft(d => d && ({ ...d, criteria: d.criteria.map((c, j) => (j === i ? { ...c, ...p } : c)) }))
  const field = 'w-full px-2.5 py-1.5 text-xs rounded outline-none'
  const fieldStyle = { background: 'var(--muted)', color: 'var(--foreground)', border: '1px solid var(--border)' }
  const total = shown ? shown.criteria.reduce((a, c) => a + (Number(c.points) || 0), 0) : 0

  return (
    <div className="p-4 md:p-8 max-w-screen-xl mx-auto">
      <PageHeader
        eyebrow="Rubric Library"
        title="Rubrics"
        sub="Manage grading rubrics. The model uses these to evaluate student submissions."
        actions={canEditRubrics && !draft ? <Button onClick={startNew}>+ New Rubric</Button> : undefined}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* List */}
        <div className="flex flex-col gap-2">
          {rubrics.length === 0 && !draft && (
            <Card><Empty title="No rubrics yet" body={canEditRubrics ? 'Create one, or upload a PDF, Word or JSON rubric below.' : 'A professor or admin will add the rubrics for this course.'} height={140} /></Card>
          )}
          {rubrics.map(r => {
            const active = (draft ? draft.id : selectedId) === r.id
            return (
              <button
                key={r.id}
                type="button"
                disabled={!!draft && draft.id !== r.id}
                onClick={() => { setSelectedId(r.id); setExpanded(0) }}
                className="rounded p-4 text-left transition-all"
                style={{ background: active ? 'rgba(59,111,255,0.08)' : 'var(--card)', border: `1px solid ${active ? 'var(--primary)' : 'var(--border)'}` }}
              >
                <div className="text-sm mb-1" style={{ color: 'var(--foreground)' }}>{r.name}</div>
                <div className="flex items-center gap-3">
                  <span className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{r.assignment}</span>
                  <span className="mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>{r.version}</span>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <span className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{r.criteria.length} criteria</span>
                  <span className="mono text-[10px]" style={{ color: 'var(--primary)' }}>{r.totalPoints} pts</span>
                </div>
              </button>
            )
          })}
          {draft && isNew && (
            <div className="rounded p-4" style={{ background: 'rgba(59,111,255,0.08)', border: '1px solid var(--primary)' }}>
              <div className="text-sm" style={{ color: 'var(--foreground)' }}>{draft.name || 'Untitled rubric'}</div>
              <div className="mono text-[10px] mt-1" style={{ color: 'var(--primary)' }}>Unsaved draft</div>
            </div>
          )}

          {canEditRubrics && (
            <div
              role="button"
              tabIndex={0}
              aria-label="Upload a PDF, Word or JSON rubric"
              onClick={() => !importing && !draft && fileRef.current?.click()}
              onKeyDown={e => { if (e.key === 'Enter' && !draft) fileRef.current?.click() }}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={e => { e.preventDefault(); setDragOver(false); if (!draft) importFile(e.dataTransfer.files[0]) }}
              className="rounded p-4 border-2 border-dashed flex flex-col items-center justify-center gap-2 cursor-pointer transition-all hover:border-[var(--primary)] hover:bg-[rgba(59,111,255,0.02)]"
              style={{ borderColor: dragOver ? 'var(--primary)' : 'var(--border)', opacity: draft ? 0.5 : 1 }}
            >
              <input ref={fileRef} type="file" className="hidden" accept=".json,.pdf,.docx,.txt,.md" onChange={e => importFile(e.target.files?.[0])} />
              {importing ? <Spinner size={20} /> : <UploadIcon size={20} />}
              <span className="text-xs text-center" style={{ color: 'var(--muted-foreground)' }}>
                {importing ? 'Reading rubric with the model…' : 'Upload PDF, Word or JSON rubric'}
              </span>
            </div>
          )}
        </div>

        {/* Detail / editor */}
        <Card className="lg:col-span-2 overflow-hidden">
          {!shown ? (
            <Empty title="Select a rubric" height={280} />
          ) : (
            <>
              <div className="px-6 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    {draft ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <label htmlFor="rb-name" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Rubric name</label>
                          <input id="rb-name" type="text" value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} className={field} style={fieldStyle} />
                        </div>
                        <div>
                          <label htmlFor="rb-assign" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Assignment</label>
                          <input id="rb-assign" type="text" value={draft.assignment} onChange={e => setDraft({ ...draft, assignment: e.target.value })} className={field} style={fieldStyle} />
                        </div>
                      </div>
                    ) : (
                      <>
                        <h2 className="text-base" style={{ color: 'var(--foreground)' }}>{shown.name}</h2>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1">
                          <span className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>by {author(shown)}</span>
                          <span className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>Updated {longDate(shown.updatedAt)}</span>
                          <span className="mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>{shown.version}</span>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-2xl" style={{ color: 'var(--primary)' }}>{total}</div>
                    <div className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>total points</div>
                  </div>
                </div>
                {draft ? (
                  <div className="mt-3">
                    <label htmlFor="rb-notes" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Notes for graders (sent to the model)</label>
                    <textarea id="rb-notes" rows={2} value={draft.instructions ?? ''} onChange={e => setDraft({ ...draft, instructions: e.target.value })} placeholder="e.g. Accept strong induction. Deduct at most 2 pts for notation." className={`${field} resize-y`} style={fieldStyle} />
                  </div>
                ) : shown.instructions ? (
                  <p className="text-xs mt-3 leading-relaxed" style={{ color: 'var(--muted-foreground)' }}><span style={{ color: 'var(--foreground)' }}>Notes for graders:</span> {shown.instructions}</p>
                ) : null}
              </div>

              <div className="p-4 md:p-6 flex flex-col gap-3">
                {shown.criteria.map((c, i) => (
                  <div key={i} className="rounded overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                    <button
                      type="button"
                      className="w-full flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-[var(--secondary)]"
                      onClick={() => setExpanded(expanded === i ? null : i)}
                      aria-expanded={expanded === i}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="mono text-[10px] w-5 h-5 rounded flex items-center justify-center shrink-0" style={{ background: 'var(--primary)', color: '#fff' }}>{i + 1}</span>
                        <div className="text-left min-w-0">
                          <div className="text-sm truncate" style={{ color: 'var(--foreground)' }}>{c.name}</div>
                          <div className="text-xs truncate" style={{ color: 'var(--muted-foreground)' }}>{c.description}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <span className="mono text-sm" style={{ color: 'var(--primary)' }}>{c.points} pts</span>
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden style={{ transform: expanded === i ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', color: 'var(--muted-foreground)' }}>
                          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                      </div>
                    </button>

                    {expanded === i && (
                      <div className="px-4 pb-4 pt-3 border-t" style={{ borderColor: 'var(--border)', background: 'var(--secondary)' }}>
                        {draft ? (
                          <div className="flex flex-col gap-3">
                            <div className="grid grid-cols-1 sm:grid-cols-[1fr_90px] gap-2">
                              <div>
                                <label htmlFor={`c-name-${i}`} className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Criterion</label>
                                <input id={`c-name-${i}`} type="text" value={c.name} onChange={e => setCrit(i, { name: e.target.value })} className={field} style={fieldStyle} />
                              </div>
                              <div>
                                <label htmlFor={`c-pts-${i}`} className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Max pts</label>
                                <input id={`c-pts-${i}`} type="number" min={0} value={c.points} onChange={e => setCrit(i, { points: Math.max(0, Number(e.target.value)) })} className={field} style={fieldStyle} />
                              </div>
                            </div>
                            <div>
                              <label htmlFor={`c-desc-${i}`} className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>What it assesses</label>
                              <input id={`c-desc-${i}`} type="text" value={c.description} onChange={e => setCrit(i, { description: e.target.value })} className={field} style={fieldStyle} />
                            </div>
                            <div className="mono text-[10px] uppercase tracking-widest" style={{ color: 'var(--muted-foreground)' }}>Levels</div>
                            {c.levels.map((l, j) => (
                              <div key={j} className="grid grid-cols-[90px_64px_1fr_24px] gap-2 items-start">
                                <input aria-label="Level name" type="text" value={l.label} onChange={e => setCrit(i, { levels: c.levels.map((x, k) => (k === j ? { ...x, label: e.target.value } : x)) })} className={field} style={fieldStyle} />
                                <input aria-label="Level points" type="number" min={0} max={c.points} value={l.points} onChange={e => setCrit(i, { levels: c.levels.map((x, k) => (k === j ? { ...x, points: Math.max(0, Number(e.target.value)) } : x)) })} className={field} style={fieldStyle} />
                                <textarea aria-label="Level description" rows={1} value={l.description} onChange={e => setCrit(i, { levels: c.levels.map((x, k) => (k === j ? { ...x, description: e.target.value } : x)) })} className={`${field} resize-y`} style={fieldStyle} />
                                <button type="button" aria-label="Remove level" onClick={() => setCrit(i, { levels: c.levels.filter((_, k) => k !== j) })} className="h-7 rounded hover:bg-[var(--card)]" style={{ color: 'var(--muted-foreground)' }}>×</button>
                              </div>
                            ))}
                            <div className="flex flex-wrap gap-2">
                              <Button kind="secondary" size="sm" onClick={() => setCrit(i, { levels: [...c.levels, { label: 'Level', points: 0, description: '' }] })}>+ Level</Button>
                              <Button kind="danger" size="sm" onClick={() => { setDraft({ ...draft, criteria: draft.criteria.filter((_, k) => k !== i) }); setExpanded(null) }}>Remove criterion</Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {c.levels.map((l, j) => (
                                <div key={j} className="rounded p-3" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
                                  <div className="flex items-center justify-between mb-1">
                                    <span className="mono text-[10px] uppercase" style={{ color: 'var(--foreground)' }}>{l.label}</span>
                                    <span className="mono text-xs" style={{ color: l.points === c.points ? '#22c55e' : l.points === 0 ? '#ef4444' : '#f59e0b' }}>{l.points} pts</span>
                                  </div>
                                  <p className="text-xs leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{l.description}</p>
                                </div>
                              ))}
                            </div>
                            {canEditRubrics && (
                              <button type="button" onClick={() => startEdit(i)} className="mt-2 px-3 py-1 text-xs rounded transition-all hover:opacity-80" style={{ background: 'var(--card)', color: 'var(--foreground)', border: '1px solid var(--border)' }}>
                                Edit criterion
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {draft && (
                  <Button kind="dashed" size="sm" onClick={() => { setDraft({ ...draft, criteria: [...draft.criteria, blankCriterion()] }); setExpanded(draft.criteria.length) }}>+ Add criterion</Button>
                )}
              </div>

              {canEditRubrics && (
                <div className="px-4 md:px-6 pb-5 flex flex-wrap gap-2">
                  {draft ? (
                    <>
                      <Button onClick={save}>{isNew ? 'Create Rubric' : 'Save Changes'}</Button>
                      <Button kind="secondary" onClick={() => { setDraft(null); setIsNew(false) }}>Cancel</Button>
                    </>
                  ) : (
                    <>
                      <Button onClick={() => startEdit()}>Edit Rubric</Button>
                      <Button kind="secondary" onClick={duplicate}>Duplicate Rubric</Button>
                      <Button kind="secondary" onClick={exportJson}>Export JSON</Button>
                      <Button kind="danger" className="sm:ml-auto" onClick={() => setConfirmDelete(true)}>Delete</Button>
                    </>
                  )}
                </div>
              )}
              {!canEditRubrics && (
                <div className="px-6 pb-5">
                  <Notice>Viewing as Teaching Assistant — contact {settings.instructor} to request rubric edits.</Notice>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      <Confirm
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        danger
        title="Delete this rubric?"
        body={`${selected?.name ?? 'This rubric'} will be removed for everyone. Grades already given with it are kept.`}
        confirmLabel="Delete rubric"
        onConfirm={remove}
      />
    </div>
  )
}
