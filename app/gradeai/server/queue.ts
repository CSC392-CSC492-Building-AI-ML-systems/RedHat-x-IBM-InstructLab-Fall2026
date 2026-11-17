import { config } from './config'
import { db, kvGet, kvSet, tx } from './db'
import { docGet, docList, docPatch, docSet, docDelete } from './docs'
import { broadcast } from './events'
import { newId } from './auth'
import {
  buildGradingPrompt, buildRubricImportPrompt, coerceRubric, gradingSchema, matchRoster, normalizeResult, parseJsonLoose,
  RUBRIC_SCHEMA, similarityPairs,
} from '../src/lib/grading'
import { DEFAULT_SETTINGS } from '../src/lib/defaults'
import type { CourseSettings, Rubric, Submission } from '../src/lib/types'

/* The queue lives in SQLite. The worker inside the Fir GPU job claims tasks over HTTPS,
   runs them on the fine-tuned model and posts results back. Nothing is graded while no
   worker is online: files simply wait. */

export function settings(): CourseSettings {
  return { ...DEFAULT_SETTINGS, ...(docGet('settings/course') ?? {}) } as CourseSettings
}

/* ---------- worker status ---------- */

export interface WorkerInfo {
  model: string | null
  slurmJobId: string | null
  node: string | null
  endsAt: number | null
  lastSeen: number
  version?: string
}

export function modelStatus() {
  const w = kvGet<WorkerInfo>('worker')
  const online = !!w && Date.now() - w.lastSeen < config.workerTimeoutSec * 1000 && (!w.endsAt || w.endsAt > Date.now())
  const counts = db.prepare(
    `SELECT SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS waiting, SUM(CASE WHEN status='leased' THEN 1 ELSE 0 END) AS grading
     FROM tasks WHERE kind = 'grade'`,
  ).get() as { waiting: number | null; grading: number | null }
  return {
    online,
    lastSeen: w?.lastSeen ?? null,
    model: w?.model ?? null,
    slurmJobId: w?.slurmJobId ?? null,
    node: w?.node ?? null,
    endsAt: w?.endsAt ?? null,
    waiting: counts.waiting ?? 0,
    grading: counts.grading ?? 0,
  }
}

let lastStatusJson = ''
/** Whether the model was online at the last check-in or maintenance tick (for the offline activity entry). */
let knownOnline = false
export function pushModelStatus(force = false) {
  const s = modelStatus()
  const j = JSON.stringify({ ...s, lastSeen: null })
  if (force || j !== lastStatusJson) { lastStatusJson = j; broadcast('model', s) }
}

export function heartbeat(info: Partial<WorkerInfo>) {
  const prev = kvGet<WorkerInfo>('worker')
  const wasOnline = modelStatus().online
  kvSet('worker', {
    model: info.model ?? prev?.model ?? null,
    slurmJobId: info.slurmJobId ?? null,
    node: info.node ?? null,
    endsAt: info.endsAt ?? null,
    version: info.version,
    lastSeen: Date.now(),
  } satisfies WorkerInfo)
  knownOnline = true
  if (!wasOnline) {
    logActivity('system', 'Grading model online', `${info.model ?? 'The fine-tuned model'} is running on Fir${info.slurmJobId ? ` (job ${info.slurmJobId})` : ''}. Waiting files will be graded now.`, 'system')
  }
  pushModelStatus()
}

/* ---------- activity ---------- */

export function logActivity(type: string, title: string, body: string, by: string) {
  const id = newId('ev')
  docSet(`activity/${id}`, { type, title, body, at: Date.now(), by })
  const all = docList('activity').sort((a, b) => Number(b.data.at) - Number(a.data.at))
  for (const a of all.slice(80)) docDelete(`activity/${a.id}`)
}

/* ---------- enqueue ---------- */

export function enqueueGrade(subId: string) {
  const sub = docGet(`submissions/${subId}`) as Submission | null
  if (!sub) return
  const rubric = docGet(`rubrics/${sub.rubricId}`) as Omit<Rubric, 'id'> | null
  if (!rubric) {
    docPatch(`submissions/${subId}`, { status: 'error', queueState: null, error: 'Its rubric was deleted. Pick a rubric and upload again.', updatedAt: Date.now() })
    return
  }
  const now = Date.now()
  tx(() => {
    db.prepare(`DELETE FROM tasks WHERE kind = 'grade' AND ref = ? AND status = 'queued'`).run(subId)
    db.prepare(`INSERT INTO tasks (id, kind, ref, payload, status, attempts, created_at, updated_at) VALUES (?, 'grade', ?, ?, 'queued', 0, ?, ?)`)
      .run(newId('t'), subId, JSON.stringify({ rubric: { ...rubric, id: sub.rubricId } }), now, now)
  })
  docPatch(`submissions/${subId}`, { status: 'pending', queueState: 'waiting', error: '', updatedAt: now })
  pushModelStatus()
}

/* ---------- rubric import (waits for the model) ---------- */

const waiters = new Map<string, { resolve: (v: unknown) => void; reject: (e: Error) => void; timer: NodeJS.Timeout }>()

export function importRubric(text: string, hint: string, timeoutMs = 150_000): Promise<Omit<Rubric, 'id' | 'createdBy' | 'updatedAt' | 'version'>> {
  const id = newId('t')
  const now = Date.now()
  db.prepare(`INSERT INTO tasks (id, kind, ref, payload, status, attempts, created_at, updated_at) VALUES (?, 'rubric', NULL, ?, 'queued', 0, ?, ?)`)
    .run(id, JSON.stringify({ text, hint }), now, now)
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      waiters.delete(id)
      db.prepare('DELETE FROM tasks WHERE id = ?').run(id)
      reject(new Error('The model did not answer in time. Try again, or upload a .json rubric.'))
    }, timeoutMs)
    waiters.set(id, {
      resolve: v => resolve(coerceRubric((v ?? {}) as Record<string, unknown>, hint)),
      reject,
      timer,
    })
  })
}

/* ---------- claim ---------- */

export interface ClaimedTask {
  id: string
  kind: 'grade' | 'rubric'
  messages: { role: 'system' | 'user'; content: string }[]
  json_schema: unknown
  max_tokens: number
  temperature: number
}

export function claim(max: number): ClaimedTask[] {
  const now = Date.now()
  const leaseUntil = now + config.leaseSec * 1000
  const rows = tx(() => {
    const picked = db.prepare(
      `SELECT id, kind, ref, payload, attempts FROM tasks
       WHERE status = 'queued' OR (status = 'leased' AND lease_until < ?)
       ORDER BY CASE kind WHEN 'rubric' THEN 0 ELSE 1 END, created_at LIMIT ?`,
    ).all(now, Math.max(1, Math.min(32, max))) as { id: string; kind: string; ref: string | null; payload: string; attempts: number }[]
    for (const t of picked) {
      db.prepare(`UPDATE tasks SET status = 'leased', lease_until = ?, attempts = attempts + 1, updated_at = ? WHERE id = ?`).run(leaseUntil, now, t.id)
    }
    return picked
  })

  const s = settings()
  const out: ClaimedTask[] = []
  for (const t of rows) {
    const payload = JSON.parse(t.payload)
    if (t.kind === 'rubric') {
      out.push({
        id: t.id, kind: 'rubric', temperature: 0, max_tokens: 3000, json_schema: RUBRIC_SCHEMA,
        messages: [{ role: 'system', content: s.systemPrompt }, { role: 'user', content: buildRubricImportPrompt(payload.text, payload.hint) }],
      })
      continue
    }
    const sub = docGet(`submissions/${t.ref}`) as Submission | null
    if (!sub) { db.prepare('DELETE FROM tasks WHERE id = ?').run(t.id); continue }
    const rubric = payload.rubric as Rubric
    const content = String((docGet(`submissionContent/${t.ref}`) ?? {}).text ?? '')
    const truncated = content.length > s.maxInputChars
    const prompt = buildGradingPrompt({
      rubric, settings: s, fileName: sub.file, text: content.slice(0, s.maxInputChars),
      detailedFeedback: sub.options?.detailed ?? true, truncated, ocr: sub.fileKind === 'scan' || sub.fileKind === 'image',
    })
    docPatch(`submissions/${t.ref}`, { queueState: 'grading', updatedAt: Date.now() })
    out.push({
      id: t.id, kind: 'grade', temperature: 0,
      max_tokens: 400 + 160 * rubric.criteria.length,
      json_schema: gradingSchema(rubric),
      messages: [{ role: 'system', content: s.systemPrompt }, { role: 'user', content: prompt }],
    })
  }
  if (rows.length) pushModelStatus()
  return out
}

/* ---------- results ---------- */

export function complete(taskId: string, ok: boolean, text: string, error: string, model: string | null) {
  const t = db.prepare('SELECT id, kind, ref, payload, attempts, status FROM tasks WHERE id = ?').get(taskId) as
    { id: string; kind: string; ref: string | null; payload: string; attempts: number; status: string } | undefined
  if (!t) return { ok: false, reason: 'unknown_task' }

  if (t.kind === 'rubric') {
    db.prepare('DELETE FROM tasks WHERE id = ?').run(taskId)
    const w = waiters.get(taskId)
    if (w) {
      clearTimeout(w.timer)
      waiters.delete(taskId)
      if (!ok) w.reject(new Error(error || 'The model could not read this rubric.'))
      else { try { w.resolve(parseJsonLoose(text)) } catch { w.reject(new Error('The model replied, but not with a readable rubric. Try again, or upload a .json rubric.')) } }
    }
    return { ok: true }
  }

  const subId = t.ref!
  const payload = JSON.parse(t.payload)
  const rubric = payload.rubric as Rubric
  const sub = docGet(`submissions/${subId}`) as Submission | null
  if (!sub) { db.prepare('DELETE FROM tasks WHERE id = ?').run(taskId); return { ok: true } }

  let result: ReturnType<typeof normalizeResult> | null = null
  let failure = error
  if (ok) {
    try { result = normalizeResult(parseJsonLoose(text), rubric) } catch { failure = 'The model replied, but the grade could not be read.' }
  }

  if (!result) {
    if (t.attempts < config.maxAttempts) {
      db.prepare(`UPDATE tasks SET status = 'queued', lease_until = NULL, error = ?, updated_at = ? WHERE id = ?`).run(failure, Date.now(), taskId)
      docPatch(`submissions/${subId}`, { queueState: 'waiting', updatedAt: Date.now() })
    } else {
      db.prepare('DELETE FROM tasks WHERE id = ?').run(taskId)
      docPatch(`submissions/${subId}`, { status: 'error', queueState: null, error: `${failure || 'Grading failed.'} Tried ${t.attempts} times — use Regrade to try again.`, updatedAt: Date.now() })
      afterGrade(sub)
    }
    pushModelStatus()
    return { ok: true }
  }

  db.prepare('DELETE FROM tasks WHERE id = ?').run(taskId)
  const s = settings()
  const roster = matchRoster(s.roster, { studentId: result.studentId, name: result.studentName, fileName: sub.file })
  const content = String((docGet(`submissionContent/${subId}`) ?? {}).text ?? '')
  const concerns = [...result.concerns]
  if (content.length > s.maxInputChars && !concerns.some(c => /truncat/i.test(c))) concerns.push('submission truncated to fit the model')
  const flagLow = sub.options?.flagLow ?? true
  let status: Submission['status'] = 'graded'
  let flag = ''
  if (flagLow && result.confidence < s.threshold) { status = 'review'; flag = `Low confidence (${result.confidence}%)${concerns.length ? ' — ' + concerns[0] : ''}` }
  else if (concerns.length) { status = 'review'; flag = concerns.join('; ') }
  else if (!s.autoApprove) { status = 'review'; flag = 'Awaiting TA sign-off (auto-approve is off)' }

  const next: Submission = {
    ...sub,
    student: roster?.name ?? (sub.student && !/^[a-z0-9_]+$/.test(sub.student) ? sub.student : result.studentName ?? sub.student),
    studentId: roster?.studentId || result.studentId || sub.studentId,
    email: roster?.email || sub.email,
    rubricName: rubric.name,
    total: rubric.totalPoints,
    score: result.score,
    aiScore: result.score,
    criteria: result.criteria,
    summary: result.summary,
    confidence: result.confidence,
    status,
    flagReason: flag,
    similarity: null,
    gradedBy: 'AI',
    gradedAt: Date.now(),
    approvedBy: null,
    approvedAt: null,
    overridden: false,
    queueState: null,
    error: '',
    model: model ?? kvGet<WorkerInfo>('worker')?.model ?? undefined,
    updatedAt: Date.now(),
  }
  const { id: _omit, ...rest } = next as Submission & { id?: string }
  void _omit
  docSet(`submissions/${subId}`, rest as unknown as Record<string, unknown>)
  pushModelStatus()
  afterGrade(next)
  return { ok: true }
}

function afterGrade(sub: Submission) {
  if (sub.batchId) checkBatch(sub.batchId)
}

/** When the last file of an upload batch is done: optional plagiarism pass, then one activity entry. */
export function checkBatch(batchId: string) {
  if (kvGet<boolean>(`batchopen:${batchId}`)) return
  const batch = docList('submissions').filter(d => d.data.batchId === batchId)
  if (!batch.length || batch.some(d => d.data.status === 'pending')) return
  const key = `batchdone:${batchId}`
  if (kvGet(key)) return
  kvSet(key, Date.now())
  const sub = batch[0].data as unknown as Submission

  let flaggedSim = 0
  if (sub.options?.plagiarism) flaggedSim = runSimilarity(sub.assignment, new Set(batch.map(b => b.id)))
  const graded = batch.filter(b => b.data.score !== null && b.data.score !== undefined)
  const failed = batch.filter(b => b.data.status === 'error').length
  const flagged = docList('submissions').filter(d => d.data.batchId === batchId && d.data.status === 'review').length
  const avg = graded.length ? graded.reduce((a, b) => a + Number(b.data.score) / Number(b.data.total || 1), 0) / graded.length * 100 : 0
  logActivity(
    'grade',
    'Batch grading complete',
    `${sub.assignment} — ${graded.length} submission${graded.length === 1 ? '' : 's'} graded against ${sub.rubricName}.${graded.length ? ` Avg score ${avg.toFixed(0)}%.` : ''}${flagged ? ` ${flagged} flagged for review.` : ''}${failed ? ` ${failed} failed.` : ''}`,
    sub.uploadedBy,
  )
  if (flaggedSim) logActivity('flag', 'Similarity flags', `${flaggedSim} submission${flaggedSim === 1 ? '' : 's'} in ${sub.assignment} share ≥70% of their text with another submission.`, sub.uploadedBy)
}

function runSimilarity(assignment: string, batchIds: Set<string>) {
  const subs = docList('submissions').filter(d => d.data.assignment === assignment)
  const texts = subs.map(d => ({ id: d.id, text: String((docGet(`submissionContent/${d.id}`) ?? {}).text ?? '') })).filter(t => t.text)
  const pairs = similarityPairs(texts, 70).filter(p => batchIds.has(p.a) || batchIds.has(p.b))
  const byId = new Map(subs.map(d => [d.id, d.data as unknown as Submission]))
  const touched = new Map<string, Submission>()
  for (const p of pairs) {
    for (const [x, y] of [[p.a, p.b], [p.b, p.a]]) {
      const s = touched.get(x) ?? byId.get(x)
      const other = byId.get(y)
      if (!s || !other) continue
      if (s.similarity && s.similarity.percent >= p.percent) continue
      touched.set(x, {
        ...s,
        status: s.status === 'graded' && s.approvedBy ? s.status : s.status === 'error' ? 'error' : 'review',
        similarity: { with: y, withName: other.student, percent: p.percent },
        flagReason: `Possible plagiarism detected — ${p.percent}% match with ${other.student} (${other.file})`,
        updatedAt: Date.now(),
      })
    }
  }
  for (const [id, s] of touched) {
    const { id: _o, ...rest } = s as Submission & { id?: string }
    void _o
    docSet(`submissions/${id}`, rest as unknown as Record<string, unknown>)
  }
  return touched.size
}

/** The worker could not reach its model: put the task back without counting it as an attempt. */
export function release(taskId: string) {
  const t = db.prepare('SELECT kind, ref FROM tasks WHERE id = ?').get(taskId) as { kind: string; ref: string | null } | undefined
  if (!t) return { ok: false }
  db.prepare(`UPDATE tasks SET status = 'queued', lease_until = NULL, attempts = MAX(attempts - 1, 0), updated_at = ? WHERE id = ?`).run(Date.now(), taskId)
  if (t.kind === 'grade' && t.ref) docPatch(`submissions/${t.ref}`, { queueState: 'waiting', updatedAt: Date.now() })
  pushModelStatus()
  return { ok: true }
}

/* ---------- maintenance ---------- */

export function cancelBatch(batchId: string) {
  const subs = docList('submissions').filter(d => d.data.batchId === batchId && d.data.status === 'pending' && d.data.queueState !== 'grading')
  for (const s of subs) {
    db.prepare(`DELETE FROM tasks WHERE kind = 'grade' AND ref = ? AND status = 'queued'`).run(s.id)
    docPatch(`submissions/${s.id}`, { status: 'error', queueState: null, error: 'Stopped before grading. Use Regrade to queue it again.', updatedAt: Date.now() })
  }
  pushModelStatus()
  return subs.length
}

export function dropTasksFor(subId: string) {
  db.prepare(`DELETE FROM tasks WHERE kind = 'grade' AND ref = ?`).run(subId)
}

/** Every 15 s: return expired leases to the queue and tell browsers when the model goes on/offline. */
export function startMaintenance() {
  knownOnline = modelStatus().online
  setInterval(() => {
    const now = Date.now()
    const expired = db.prepare(`SELECT id, ref, attempts FROM tasks WHERE status = 'leased' AND lease_until < ?`).all(now) as { id: string; ref: string | null; attempts: number }[]
    for (const t of expired) {
      db.prepare(`UPDATE tasks SET status = 'queued', lease_until = NULL, updated_at = ? WHERE id = ?`).run(now, t.id)
      if (t.ref) docPatch(`submissions/${t.ref}`, { queueState: 'waiting', updatedAt: now })
    }
    const online = modelStatus().online
    if (knownOnline && !online) {
      const w = kvGet<WorkerInfo>('worker')
      const waiting = modelStatus().waiting
      logActivity('system', 'Grading model offline', `The Fir job${w?.slurmJobId ? ` ${w.slurmJobId}` : ''} stopped.${waiting ? ` ${waiting} file${waiting === 1 ? ' is' : 's are'} waiting and will be graded when it's back.` : ''}`, 'system')
    }
    knownOnline = online
    pushModelStatus()
  }, 15_000)
}
