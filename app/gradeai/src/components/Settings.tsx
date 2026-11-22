import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ROLE_COLORS, ROLE_LABELS, useApp, usePerms } from '../context'
import type { CourseSettings, Member, Role, RosterEntry } from '../lib/types'
import { api, ApiError } from '../lib/api'
import ModelBadge from './ModelBadge'
import { parseCSV } from '../lib/format'
import { readText } from '../lib/files'
import { matchRoster } from '../lib/grading'
import { useAssignments } from './assignments'
import { Avatar, Button, Checkbox, Confirm, Notice, Spinner } from './ui'

export default function Settings() {
  const app = useApp()
  const { settings, saveSettings, saveSubmission, submissions, rubrics, notify, me, model, ocr } = app
  const perms = usePerms()
  const editable = perms.canEditSettings
  const [form, setForm] = useState<CourseSettings>(settings)
  const [saving, setSaving] = useState(false)
  const [danger, setDanger] = useState<'' | 'reset' | 'delete'>('')
  const [working, setWorking] = useState('')
  const rosterRef = useRef<HTMLInputElement>(null)
  const assignments = useAssignments()

  useEffect(() => { setForm(settings) }, [settings])
  const dirty = JSON.stringify({ ...form, updatedAt: 0 }) !== JSON.stringify({ ...settings, updatedAt: 0 })
  const set = <K extends keyof CourseSettings>(k: K, v: CourseSettings[K]) => setForm(f => ({ ...f, [k]: v }))

  async function save() {
    setSaving(true)
    try {
      await saveSettings({ ...form, enrollment: Math.max(0, Math.round(Number(form.enrollment) || 0)) })
      notify('Settings saved.')
      if (form.roster.length && JSON.stringify(form.roster) !== JSON.stringify(settings.roster)) {
        let n = 0
        for (const s of submissions) {
          const r = matchRoster(form.roster, { studentId: s.studentId, name: s.student, fileName: s.file })
          if (r && (r.name !== s.student || (r.studentId && r.studentId !== s.studentId) || (r.email && r.email !== s.email))) {
            await saveSubmission({ ...s, student: r.name || s.student, studentId: r.studentId || s.studentId, email: r.email || s.email }).catch(() => undefined)
            n++
          }
        }
        if (n) notify(`Matched ${n} existing submission${n === 1 ? '' : 's'} to the roster.`)
      }
    } catch { /* toast shown */ } finally { setSaving(false) }
  }

  async function importRoster(f: File | undefined) {
    if (!f) return
    try {
      const rows = parseCSV(await readText(f))
      if (rows.length < 2) { notify('That roster has no rows.', 'warn'); return }
      const head = rows[0].map(h => h.toLowerCase().trim())
      const col = (...names: string[]) => head.findIndex(h => names.some(n => h.includes(n)))
      const iName = col('name'), iFirst = col('first'), iLast = col('last', 'surname'), iEmail = col('email', 'e-mail')
      const iId = col('student id', 'student number', 'studentid', 'student_number', 'sis', 'id'), iUtor = col('utorid', 'username', 'login')
      const roster: RosterEntry[] = rows.slice(1).map(r => ({
        name: (iName >= 0 && !(iFirst >= 0 && iName === iFirst) ? r[iName] : [r[iFirst] ?? '', r[iLast] ?? ''].join(' ')).trim(),
        email: (iEmail >= 0 ? r[iEmail] : '').trim(),
        studentId: (iId >= 0 && iId !== iEmail && iId !== iUtor ? r[iId] : '').trim(),
        utorid: (iUtor >= 0 ? r[iUtor] : '').trim(),
      })).filter(r => r.name || r.email || r.studentId)
      if (!roster.length) { notify('No students found. The file needs Name, Email and Student ID columns.', 'warn'); return }
      setForm(f2 => ({ ...f2, roster, enrollment: roster.length }))
      notify(`${roster.length} students read. Save settings to keep the roster.`)
    } catch {
      notify('Could not read that file. Upload a .csv export from Quercus, ACORN or Crowdmark.', 'error')
    } finally {
      if (rosterRef.current) rosterRef.current.value = ''
    }
  }

  async function resetGrades() {
    setWorking('Resetting grades…')
    try {
      const r = await api<{ deleted: number }>('/admin/reset', { body: { assignment: settings.currentAssignment } })
      notify(`${r.deleted} submissions deleted.`)
    } catch (e) { notify(e instanceof ApiError ? e.message : 'Reset failed.', 'error') } finally { setWorking('') }
  }

  async function deleteCourse() {
    setWorking('Deleting course data…')
    try {
      const r = await api<{ deleted: number }>('/admin/wipe', { body: {} })
      notify(`Course data deleted (${r.deleted} submissions).`)
    } catch (e) { notify(e instanceof ApiError ? e.message : 'Delete failed.', 'error') } finally { setWorking('') }
  }

  const stats = useMemo(() => {
    const ai = submissions.filter(s => s.aiScore !== null)
    const reviewed = ai.filter(s => s.approvedBy || s.overridden)
    const overridden = ai.filter(s => s.overridden)
    const avgConf = ai.length ? Math.round(ai.reduce((a, s) => a + (s.confidence ?? 0), 0) / ai.length) : null
    const agreement = reviewed.length ? Math.round(((reviewed.length - overridden.length) / reviewed.length) * 100) : null
    return { ai: ai.length, avgConf, agreement, overridden: overridden.length, reviewed: reviewed.length }
  }, [submissions])

  const fieldsDisabled = !editable

  return (
    <div className="p-4 md:p-8 max-w-screen-xl mx-auto">
      <div className="mb-8">
        <div className="text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted-foreground)' }}>Configuration</div>
        <h1 className="text-2xl tracking-tight" style={{ color: 'var(--foreground)' }}>Settings</h1>
        {!editable && <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>Only professors and administrators can change course settings.</p>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col gap-4">
          <Section title="Course">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field id="s-code" label="Course Code" value={form.code} onChange={v => set('code', v)} disabled={fieldsDisabled} />
              <Field id="s-term" label="Term" value={form.term} onChange={v => set('term', v)} disabled={fieldsDisabled} />
            </div>
            <Field id="s-name" label="Course Name" value={form.name} onChange={v => set('name', v)} disabled={fieldsDisabled} />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field id="s-instr" label="Instructor" value={form.instructor} onChange={v => set('instructor', v)} disabled={fieldsDisabled} />
              <div>
                <label htmlFor="s-current" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>Current assignment</label>
                <input id="s-current" list="assignment-list" type="text" value={form.currentAssignment} disabled={fieldsDisabled} onChange={e => set('currentAssignment', e.target.value)} className="w-full px-3 py-2 text-sm rounded outline-none" style={inputStyle(fieldsDisabled)} />
                <datalist id="assignment-list">{assignments.map(a => <option key={a} value={a} />)}</datalist>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
              <Field id="s-enrol" label="Enrollment" value={String(form.enrollment)} onChange={v => set('enrollment', Number(v.replace(/\D/g, '')) || 0)} disabled={fieldsDisabled || form.roster.length > 0} suffix="students" />
              <div className="flex flex-col gap-1">
                <div className="mono text-[10px] uppercase tracking-widest" style={{ color: 'var(--muted-foreground)' }}>Class roster</div>
                <div className="flex items-center gap-2">
                  <input ref={rosterRef} type="file" accept=".csv,.txt" className="hidden" onChange={e => importRoster(e.target.files?.[0])} />
                  <Button kind="secondary" size="sm" disabled={fieldsDisabled} onClick={() => rosterRef.current?.click()}>{form.roster.length ? 'Replace roster' : 'Upload roster CSV'}</Button>
                  {form.roster.length > 0 && (
                    <>
                      <span className="mono text-[11px]" style={{ color: 'var(--muted-foreground)' }}>{form.roster.length} students</span>
                      {editable && <button type="button" className="mono text-[10px] hover:opacity-70" style={{ color: '#ef4444' }} onClick={() => setForm(f => ({ ...f, roster: [] }))}>Clear</button>}
                    </>
                  )}
                </div>
              </div>
            </div>
            <div className="text-[11px] leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              The roster (Name, Email, Student ID, UTORid columns) matches uploaded files to students and fills the Crowdmark export.
            </div>
          </Section>

          <Section title="AI Grading Model">
            <ModelBadge detailed />
            <div className="text-[11px] leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              Your fine-tuned model runs in a GPU job on Fir. Start it with <span className="mono">sbatch ~/gradeai/gradeai-model.sbatch</span>; while no job is running, uploads wait in the queue.
            </div>
            <div>
              <label htmlFor="s-system" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>System prompt sent with every request</label>
              <textarea id="s-system" rows={4} value={form.systemPrompt} readOnly={fieldsDisabled} onChange={e => set('systemPrompt', e.target.value)} className="w-full px-3 py-2 text-xs leading-relaxed rounded outline-none resize-y" style={inputStyle(fieldsDisabled)} />
              <div className="text-[11px] mt-1 leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>Match the system prompt your InstructLab training data used, so the model behaves as it did in training.</div>
            </div>
            <div className="max-w-sm">
              <Field id="s-maxchars" label="Max submission length" value={String(form.maxInputChars)} onChange={v => set('maxInputChars', Math.max(1000, Number(v.replace(/\D/g, '')) || 0))} disabled={fieldsDisabled} suffix="characters" />
              <div className="text-[11px] mt-1 leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>Longer files are cut and flagged for review. Keep this near 3 × the job's MAX_MODEL_LEN.</div>
            </div>
            <div className="text-[11px]" style={{ color: ocr.backend === 'gemini' || ocr.tesseract ? 'var(--muted-foreground)' : '#b45309' }}>
              {ocr.backend === 'gemini'
                ? 'Scanned and photographed work is transcribed using the Gemini VLM.'
                : ocr.tesseract
                ? 'Scanned and photographed work is read on this server with Tesseract OCR.'
                : 'OCR is not configured on the server (set GEMINI_API_KEY in .env or install tesseract-ocr and poppler-utils).'}
            </div>
          </Section>

          <Section title="Confidence Thresholds">
            <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>Grades below the confidence threshold are flagged for TA review.</div>
            <div>
              <div className="flex justify-between mono text-[11px] mb-2" style={{ color: 'var(--muted-foreground)' }}>
                <label htmlFor="s-threshold">Review threshold</label>
                <span style={{ color: 'var(--foreground)' }}>{form.threshold}%</span>
              </div>
              <input id="s-threshold" type="range" min={50} max={95} value={form.threshold} disabled={fieldsDisabled} onChange={e => set('threshold', Number(e.target.value))} className="w-full accent-[var(--primary)]" />
            </div>
            <div>
              <Checkbox id="s-auto" checked={form.autoApprove} disabled={fieldsDisabled} onChange={v => set('autoApprove', v)} label="Auto-approve above threshold" />
              <Checkbox id="s-signoff" checked={form.requireSignoff} disabled={fieldsDisabled} onChange={v => set('requireSignoff', v)} label="Require TA sign-off before Crowdmark export" />
              <Checkbox id="s-plag" checked={form.plagiarism} disabled={fieldsDisabled} onChange={v => set('plagiarism', v)} label="Run plagiarism detection on each batch" />
            </div>
            <div className="max-w-xs">
              <Field id="s-minutes" label="Manual grading time (for Time Saved)" value={String(form.minutesPerManualGrade)} onChange={v => set('minutesPerManualGrade', Math.max(0, Number(v.replace(/[^\d.]/g, '')) || 0))} disabled={fieldsDisabled} suffix="min / submission" />
            </div>
          </Section>

          <TeamSection meId={me.id} canManage={perms.canManageTeam} />

          {editable && (
            <div className="flex items-center gap-3">
              <Button onClick={save} disabled={!dirty || saving}>{saving ? <><Spinner light size={12} /> Saving…</> : 'Save Settings'}</Button>
              {dirty && <span className="mono text-[11px]" style={{ color: 'var(--muted-foreground)' }}>Unsaved changes</span>}
            </div>
          )}
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          <AccountSection />

          <Section title="Crowdmark">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ background: '#22c55e' }} />
              <span className="text-xs" style={{ color: '#16a34a' }}>CSV export ready</span>
            </div>
            <Field id="s-cm-course" label="Crowdmark course" value={form.crowdmarkCourse} onChange={v => set('crowdmarkCourse', v)} disabled={fieldsDisabled} />
            <Field id="s-cm-inst" label="Institution" value={form.institution} onChange={v => set('institution', v)} disabled={fieldsDisabled} />
            <div className="text-[11px] leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              GradeAI writes grades in Crowdmark's layout. Upload the file in Crowdmark or your LMS gradebook to release them.
            </div>
          </Section>

          <Section title="Model Info">
            <div className="flex flex-col gap-2 text-xs">
              {[
                { label: 'Model', value: model.model ?? '—' },
                { label: 'Status', value: model.online ? `Online${model.slurmJobId ? ` · job ${model.slurmJobId}` : ''}` : 'Offline' },
                { label: 'AI-graded submissions', value: String(stats.ai) },
                { label: 'Avg confidence', value: stats.avgConf === null ? '—' : `${stats.avgConf}%` },
                { label: 'TA agreement', value: stats.agreement === null ? '—' : `${stats.agreement}% of ${stats.reviewed}` },
                { label: 'Scores overridden', value: String(stats.overridden) },
              ].map(r => (
                <div key={r.label} className="flex justify-between py-1 border-b gap-3" style={{ borderColor: 'var(--border)' }}>
                  <span style={{ color: 'var(--muted-foreground)' }}>{r.label}</span>
                  <span className="mono" style={{ color: 'var(--foreground)' }}>{r.value}</span>
                </div>
              ))}
              <div className="text-[11px] leading-relaxed pt-1" style={{ color: 'var(--muted-foreground)' }}>
                TA agreement counts reviewed grades that kept the model's score — a running check on how well the fine-tuned model matches your TAs.
              </div>
            </div>
          </Section>

          <Section title="Danger Zone">
            <div className="flex flex-col gap-2">
              <Button kind="danger" size="sm" className="w-full" disabled={!perms.canDanger || !!working} onClick={() => setDanger('reset')}>
                Reset all grades ({shortA(settings.currentAssignment)})
              </Button>
              <Button kind="danger" size="sm" className="w-full" disabled={!perms.canDanger || !!working} onClick={() => setDanger('delete')}>
                Delete course data
              </Button>
              {working && <div className="mono text-[10px] text-center flex items-center justify-center gap-2" style={{ color: 'var(--muted-foreground)' }}><Spinner size={10} /> {working}</div>}
              {!perms.canDanger && <div className="mono text-[10px] text-center" style={{ color: 'var(--muted-foreground)' }}>Admin role required</div>}
            </div>
          </Section>
        </div>
      </div>

      <Confirm
        open={danger === 'reset'}
        onClose={() => setDanger('')}
        danger
        title={`Reset all grades for ${settings.currentAssignment}?`}
        body={`This deletes all ${submissions.filter(s => s.assignment === settings.currentAssignment).length} submissions and grades for ${settings.currentAssignment} for everyone. Rubrics are kept. This can't be undone.`}
        confirmLabel="Delete grades"
        typeToConfirm="RESET"
        onConfirm={resetGrades}
      />
      <Confirm
        open={danger === 'delete'}
        onClose={() => setDanger('')}
        danger
        title="Delete all course data?"
        body={`This deletes every submission (${submissions.length}), rubric (${rubrics.length}), export record and activity item. Course settings and the team are kept. This can't be undone.`}
        confirmLabel="Delete everything"
        typeToConfirm="DELETE"
        onConfirm={deleteCourse}
      />
    </div>
  )
}

function shortA(a: string) {
  const m = a.match(/(\d+)/)
  return /assignment/i.test(a) && m ? `A${m[1]}` : a
}

function TeamSection({ meId, canManage }: { meId: string; canManage: boolean }) {
  const { users, refreshUsers, notify } = useApp()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [newRole, setNewRole] = useState<Role>('ta')
  const [link, setLink] = useState<{ who: string; url: string } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { refreshUsers() }, [refreshUsers])

  async function invite() {
    setBusy(true)
    try {
      const r = await api<{ user: Member; inviteUrl: string }>('/users', { body: { name, email, role: newRole } })
      setLink({ who: r.user.name, url: r.inviteUrl })
      setName(''); setEmail(''); setAdding(false)
      await refreshUsers()
    } catch (e) { notify(e instanceof ApiError ? e.message : 'Could not add that person.', 'error') } finally { setBusy(false) }
  }

  async function setRole(id: string, role: Role) {
    try { await api(`/users/${id}`, { method: 'PATCH', body: { role } }); await refreshUsers(); notify('Role updated.') }
    catch (e) { notify(e instanceof ApiError ? e.message : 'Could not change the role.', 'error') }
  }

  async function resetLink(m: Member) {
    try { const r = await api<{ inviteUrl: string }>(`/users/${m.id}/reset`, { body: {} }); setLink({ who: m.name, url: r.inviteUrl }); await refreshUsers() }
    catch (e) { notify(e instanceof ApiError ? e.message : 'Could not make a new link.', 'error') }
  }

  async function remove(m: Member) {
    try { await api(`/users/${m.id}`, { method: 'DELETE' }); await refreshUsers(); notify(`${m.name} removed.`) }
    catch (e) { notify(e instanceof ApiError ? e.message : 'Could not remove them.', 'error') }
  }

  const order: Role[] = ['admin', 'professor', 'ta']
  const sorted = [...users].sort((a, b) => order.indexOf(a.role) - order.indexOf(b.role) || a.name.localeCompare(b.name))
  const fieldStyle = { background: 'var(--background)', border: '1px solid var(--border)' }

  return (
    <Section title="Team">
      <div className="flex flex-col gap-2">
        {sorted.map(m => (
          <MemberRow
            key={m.id}
            name={m.id === meId ? `${m.name} (you)` : m.name}
            sub={m.status === 'invited' ? `${m.email} · invite not accepted yet` : m.email}
            color={ROLE_COLORS[m.role]}
            role={m.role}
            onRole={canManage ? r => setRole(m.id, r) : undefined}
            onReset={canManage && m.id !== meId ? () => resetLink(m) : undefined}
            onRemove={canManage && m.id !== meId ? () => remove(m) : undefined}
            invited={m.status === 'invited'}
          />
        ))}
      </div>
      {link && (
        <Notice kind="ok">
          <div className="mb-2">Send this sign-in link to {link.who}. It works once and expires in 7 days.</div>
          <div className="flex gap-2 items-center">
            <input readOnly value={link.url} aria-label="Invite link" onFocus={e => e.currentTarget.select()} className="flex-1 min-w-0 mono text-[11px] px-2 py-1.5 rounded outline-none" style={{ background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
            <Button size="sm" kind="secondary" onClick={() => navigator.clipboard.writeText(link.url).then(() => notify('Link copied.')).catch(() => notify('Select the link and copy it.', 'warn'))}>Copy</Button>
            <Button size="sm" kind="ghost" onClick={() => setLink(null)}>Done</Button>
          </div>
        </Notice>
      )}
      {canManage && !adding && <Button kind="dashed" size="sm" className="self-start" onClick={() => setAdding(true)}>+ Invite team member</Button>}
      {adding && (
        <div className="rounded p-3 flex flex-col gap-2" style={{ background: 'var(--secondary)' }}>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2">
            <input aria-label="Name" placeholder="Name" value={name} onChange={e => setName(e.target.value)} className="px-3 py-2 text-sm rounded outline-none" style={fieldStyle} />
            <input aria-label="Email" placeholder="Email" type="email" value={email} onChange={e => setEmail(e.target.value)} className="px-3 py-2 text-sm rounded outline-none" style={fieldStyle} />
            <select aria-label="Role" value={newRole} onChange={e => setNewRole(e.target.value as Role)} className="px-2 py-2 text-xs rounded outline-none" style={fieldStyle}>
              {(['ta', 'professor', 'admin'] as Role[]).map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </select>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={invite} disabled={busy || !name.trim() || !email.trim()}>{busy ? <Spinner light size={12} /> : 'Create invite link'}</Button>
            <Button size="sm" kind="ghost" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
          <div className="text-[11px] leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>GradeAI doesn't send email: you'll get a link to pass on yourself.</div>
        </div>
      )}
    </Section>
  )
}

function AccountSection() {
  const { me, notify, signOut } = useApp()
  const [open, setOpen] = useState(false)
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  async function change() {
    setBusy(true)
    try {
      await api('/me/password', { body: { current, next } })
      notify('Password changed.')
      setOpen(false); setCurrent(''); setNext('')
    } catch (e) { notify(e instanceof ApiError ? e.message : 'Could not change the password.', 'error') } finally { setBusy(false) }
  }
  const fieldStyle = { background: 'var(--muted)', border: '1px solid var(--border)' }
  return (
    <Section title="Your account">
      <div className="text-sm" style={{ color: 'var(--foreground)' }}>{me.name}</div>
      <div className="mono text-[10px] -mt-2" style={{ color: 'var(--muted-foreground)' }}>{me.email}</div>
      {open ? (
        <div className="flex flex-col gap-2">
          <input type="password" aria-label="Current password" placeholder="Current password" autoComplete="current-password" value={current} onChange={e => setCurrent(e.target.value)} className="px-3 py-2 text-sm rounded outline-none" style={fieldStyle} />
          <input type="password" aria-label="New password" placeholder="New password (10+ characters)" autoComplete="new-password" value={next} onChange={e => setNext(e.target.value)} className="px-3 py-2 text-sm rounded outline-none" style={fieldStyle} />
          <div className="flex gap-2">
            <Button size="sm" onClick={change} disabled={busy || next.length < 10 || !current}>Change password</Button>
            <Button size="sm" kind="ghost" onClick={() => setOpen(false)}>Cancel</Button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" kind="secondary" onClick={() => setOpen(true)}>Change password</Button>
          <Button size="sm" kind="secondary" onClick={signOut}>Sign out</Button>
        </div>
      )}
    </Section>
  )
}

function MemberRow({ name, sub, color, role, avatar, onRole, onRemove, onReset, invited }: { name: string; sub: string; color: string; role: Role; avatar?: string | null; onRole?: (r: Role) => void; onRemove?: () => void; onReset?: () => void; invited?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-3 p-3 rounded" style={{ background: 'var(--secondary)', opacity: invited ? 0.8 : 1 }}>
      <Avatar name={name} color={color} url={avatar} />
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate" style={{ color: 'var(--foreground)' }}>{name}</div>
        <div className="mono text-[10px] truncate" style={{ color: 'var(--muted-foreground)' }}>{sub}</div>
      </div>
      {onRole ? (
        <select aria-label={`Role for ${name}`} value={role} onChange={e => onRole(e.target.value as Role)} className="mono text-[10px] px-2 py-1 rounded outline-none" style={{ background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}>
          {(['ta', 'professor', 'admin'] as Role[]).map(r => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
        </select>
      ) : (
        <span className="mono text-[10px] px-2 py-0.5 rounded whitespace-nowrap" style={{ background: 'var(--card)', color: 'var(--muted-foreground)' }}>{ROLE_LABELS[role]}</span>
      )}
      {onReset && <button type="button" onClick={onReset} className="mono text-[10px] hover:opacity-70 transition-opacity whitespace-nowrap" style={{ color: 'var(--primary)' }}>{invited ? 'New link' : 'Reset password'}</button>}
      {onRemove && <button type="button" onClick={onRemove} className="mono text-[10px] hover:opacity-70 transition-opacity" style={{ color: '#ef4444' }}>Remove</button>}
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded p-5" style={{ background: 'var(--card)', border: '1px solid var(--border)', borderLeft: '3px solid var(--primary)' }}>
      <h2 className="text-xs uppercase tracking-widest mb-4" style={{ color: 'var(--primary)' }}>{title}</h2>
      <div className="flex flex-col gap-3">{children}</div>
    </section>
  )
}

function inputStyle(disabled: boolean) {
  return { background: disabled ? 'var(--secondary)' : 'var(--muted)', color: 'var(--foreground)', border: '1px solid var(--border)', cursor: disabled ? 'default' : 'text' }
}

function Field({ id, label, value, onChange, disabled, suffix }: { id: string; label: string; value: string; onChange: (v: string) => void; disabled?: boolean; suffix?: string }) {
  return (
    <div>
      <label htmlFor={id} className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</label>
      <div className="relative">
        <input id={id} type="text" value={value} readOnly={disabled} onChange={e => onChange(e.target.value)} className="w-full px-3 py-2 text-sm rounded outline-none transition-all" style={{ ...inputStyle(!!disabled), paddingRight: suffix ? 110 : undefined }} />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 mono text-[10px] pointer-events-none" style={{ color: 'var(--muted-foreground)' }}>{suffix}</span>}
      </div>
    </div>
  )
}
