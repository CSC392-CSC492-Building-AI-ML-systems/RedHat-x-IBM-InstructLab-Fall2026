import fs from 'node:fs'
import path from 'node:path'
import express, { type NextFunction, type Request, type Response } from 'express'
import multer from 'multer'
import { config } from './config'
import { db, kvSet } from './db'
import {
  clearFailures, createSession, destroySession, findInvite, hashPassword, loadUser, makeInvite, newId, noteFailure,
  passwordProblem, requireAppHeader, requireRole, requireUser, throttled, verifyPassword, workerAuth, type Role,
} from './auth'
import { docDelete, docGet, docList, docPatch, docSet, docsRouter } from './docs'
import { addClient, disconnectUser } from './events'
import { sendStoredFile } from './file-serving'
import { ocrFileAuto, ocrTools, ocrBackend } from './ocr'
import {
  cancelBatch, checkBatch, claim, complete, release, dropTasksFor, enqueueGrade, heartbeat, importRubric, logActivity, modelStatus, settings, startMaintenance,
} from './queue'
import { matchRoster } from '../src/lib/grading'
import { DEFAULT_SETTINGS, SEED_RUBRICS } from '../src/lib/defaults'
import type { Submission } from '../src/lib/types'

const app = express()
app.disable('x-powered-by')
if (config.trustProxy) app.set('trust proxy', 1)

app.use((_req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.setHeader('Referrer-Policy', 'same-origin')
  res.setHeader('X-Frame-Options', 'DENY')
  res.setHeader(
    'Content-Security-Policy',
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
  )
  next()
})

const api = express.Router()
app.use('/api', api)

/* ================= worker (Fir) ================= */
const worker = express.Router()
worker.use(express.json({ limit: '4mb' }), workerAuth)

worker.post('/heartbeat', (req, res) => {
  const b = req.body ?? {}
  heartbeat({
    model: b.model ? String(b.model) : null,
    slurmJobId: b.slurmJobId ? String(b.slurmJobId) : null,
    node: b.node ? String(b.node) : null,
    endsAt: Number(b.endsAt) || null,
    version: b.version ? String(b.version) : undefined,
  })
  res.json({ ok: true, ...modelStatus() })
})

worker.post('/claim', (req, res) => {
  const b = req.body ?? {}
  heartbeat({ model: b.model ?? null, slurmJobId: b.slurmJobId ?? null, node: b.node ?? null, endsAt: Number(b.endsAt) || null, version: b.version })
  res.json({ tasks: claim(Number(b.max) || 4) })
})

worker.post('/result', (req, res) => {
  const b = req.body ?? {}
  res.json(complete(String(b.id), !!b.ok, String(b.content ?? ''), String(b.error ?? ''), b.model ? String(b.model) : null))
})

worker.post('/release', (req, res) => { res.json(release(String(req.body?.id ?? ''))) })

api.use('/worker', worker)

/* ================= browser API ================= */
api.use(express.json({ limit: '6mb' }), loadUser, requireAppHeader)

/* ---- setup / auth ---- */
const userCount = () => (db.prepare('SELECT COUNT(*) AS n FROM users').get() as { n: number }).n

api.get('/setup', (_req, res) => { res.json({ needsSetup: userCount() === 0 }) })

api.post('/setup', (req, res) => {
  if (userCount() > 0) { res.status(409).json({ error: 'done', message: 'This GradeAI server is already set up. Sign in instead.' }); return }
  const { name, email, password } = req.body ?? {}
  const p = passwordProblem(password)
  if (!name || !email || !/^\S+@\S+\.\S+$/.test(String(email))) { res.status(400).json({ error: 'bad_request', message: 'Enter your name and a valid email.' }); return }
  if (p) { res.status(400).json({ error: 'weak_password', message: p }); return }
  const id = newId('u')
  db.prepare('INSERT INTO users (id, email, name, role, pw_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)')
    .run(id, String(email).trim().toLowerCase(), String(name).trim(), 'admin', hashPassword(password), Date.now())
  // Starter data: the course settings and the two Assignment 2 rubrics from the prototype (editable/deletable).
  if (!docGet('settings/course')) docSet('settings/course', { ...DEFAULT_SETTINGS, updatedAt: Date.now() })
  if (!docList('rubrics').length) for (const r of SEED_RUBRICS) { const { id: rid, ...rest } = r; docSet(`rubrics/${rid}`, rest as unknown as Record<string, unknown>) }
  createSession(res, id)
  res.json({ ok: true })
})

api.post('/login', (req, res) => {
  const email = String(req.body?.email ?? '').trim().toLowerCase()
  const key = `${req.ip}|${email}`
  if (throttled(key)) { res.status(429).json({ error: 'throttled', message: 'Too many attempts. Wait 10 minutes and try again.' }); return }
  const u = db.prepare('SELECT id, pw_hash FROM users WHERE email = ?').get(email) as { id: string; pw_hash: string | null } | undefined
  if (!u || !verifyPassword(String(req.body?.password ?? ''), u.pw_hash)) {
    noteFailure(key)
    res.status(401).json({ error: 'bad_login', message: 'That email and password don’t match an account.' })
    return
  }
  clearFailures(key)
  createSession(res, u.id)
  res.json({ ok: true })
})

api.post('/logout', (req, res) => { destroySession(req, res); res.json({ ok: true }) })

api.get('/invite/:token', (req, res) => {
  const u = findInvite(req.params.token)
  if (!u || u.invite_expires < Date.now()) { res.status(404).json({ error: 'expired', message: 'This invite link has expired or was already used. Ask an admin for a new one.' }); return }
  res.json({ name: u.name, email: u.email, role: u.role })
})

api.post('/invite/:token', (req, res) => {
  const u = findInvite(req.params.token)
  if (!u || u.invite_expires < Date.now()) { res.status(404).json({ error: 'expired', message: 'This invite link has expired or was already used.' }); return }
  const p = passwordProblem(req.body?.password)
  if (p) { res.status(400).json({ error: 'weak_password', message: p }); return }
  db.prepare('UPDATE users SET pw_hash = ?, invite_hash = NULL, invite_expires = NULL WHERE id = ?').run(hashPassword(req.body.password), u.id)
  db.prepare('DELETE FROM sessions WHERE user_id = ?').run(u.id)
  createSession(res, u.id)
  res.json({ ok: true })
})

api.get('/me', (req, res) => { res.json({ user: req.user ?? null, ocr: { ...ocrTools, backend: ocrBackend } }) })

api.post('/me/password', requireUser, (req, res) => {
  const row = db.prepare('SELECT pw_hash FROM users WHERE id = ?').get(req.user!.id) as { pw_hash: string }
  if (!verifyPassword(String(req.body?.current ?? ''), row.pw_hash)) { res.status(400).json({ error: 'bad_login', message: 'Your current password is wrong.' }); return }
  const p = passwordProblem(req.body?.next)
  if (p) { res.status(400).json({ error: 'weak_password', message: p }); return }
  db.prepare('UPDATE users SET pw_hash = ? WHERE id = ?').run(hashPassword(req.body.next), req.user!.id)
  res.json({ ok: true })
})

/* ---- everything below needs a signed-in user ---- */
api.use(requireUser)

api.get('/events', (req, res) => {
  addClient(res, req.user!.id)
  res.write(`event: model\ndata: ${JSON.stringify(modelStatus())}\n\n`)
})

api.use(docsRouter())

api.get('/model', (_req, res) => { res.json(modelStatus()) })

/* ---- team ---- */
function members() {
  return (db.prepare('SELECT id, email, name, role, pw_hash IS NOT NULL AS active, last_login FROM users ORDER BY created_at').all() as
    { id: string; email: string; name: string; role: Role; active: number; last_login: number | null }[])
    .map(u => ({ id: u.id, email: u.email, name: u.name, role: u.role, status: u.active ? 'active' : 'invited', lastLogin: u.last_login }))
}
const ROLES = new Set(['admin', 'professor', 'ta'])

api.get('/users', (_req, res) => { res.json({ users: members() }) })

api.post('/users', requireRole('admin'), (req, res) => {
  const name = String(req.body?.name ?? '').trim()
  const email = String(req.body?.email ?? '').trim().toLowerCase()
  const role = String(req.body?.role ?? 'ta')
  if (!name || !/^\S+@\S+\.\S+$/.test(email) || !ROLES.has(role)) { res.status(400).json({ error: 'bad_request', message: 'Enter a name, a valid email and a role.' }); return }
  if (db.prepare('SELECT 1 FROM users WHERE email = ?').get(email)) { res.status(409).json({ error: 'exists', message: 'Someone with that email is already on the team.' }); return }
  const id = newId('u')
  db.prepare('INSERT INTO users (id, email, name, role, created_at) VALUES (?, ?, ?, ?, ?)').run(id, email, name, role, Date.now())
  res.json({ user: members().find(m => m.id === id), inviteUrl: makeInvite(id) })
})

api.patch('/users/:id', requireRole('admin'), (req, res) => {
  const role = req.body?.role
  if (role !== undefined && !ROLES.has(role)) { res.status(400).json({ error: 'bad_request' }); return }
  if (req.params.id === req.user!.id && role && role !== 'admin') {
    const admins = (db.prepare(`SELECT COUNT(*) AS n FROM users WHERE role = 'admin'`).get() as { n: number }).n
    if (admins < 2) { res.status(400).json({ error: 'last_admin', message: 'You are the only administrator. Make someone else an admin first.' }); return }
  }
  if (role) db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, req.params.id)
  if (req.body?.name) db.prepare('UPDATE users SET name = ? WHERE id = ?').run(String(req.body.name).trim(), req.params.id)
  res.json({ users: members() })
})

api.post('/users/:id/reset', requireRole('admin'), (req, res) => {
  if (!db.prepare('SELECT 1 FROM users WHERE id = ?').get(req.params.id)) { res.status(404).json({ error: 'not_found' }); return }
  db.prepare('UPDATE users SET pw_hash = NULL WHERE id = ?').run(req.params.id)
  db.prepare('DELETE FROM sessions WHERE user_id = ?').run(req.params.id)
  disconnectUser(req.params.id)
  res.json({ inviteUrl: makeInvite(req.params.id) })
})

api.delete('/users/:id', requireRole('admin'), (req, res) => {
  if (req.params.id === req.user!.id) { res.status(400).json({ error: 'self', message: 'You can’t remove yourself.' }); return }
  db.prepare('DELETE FROM users WHERE id = ?').run(req.params.id)
  disconnectUser(req.params.id)
  res.json({ users: members() })
})

/* ---- uploads ---- */
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: config.maxUploadMb * 1024 * 1024, files: 500 } })

interface UploadMeta {
  rubricId: string
  batchId?: string
  final?: boolean
  options: { flagLow: boolean; detailed: boolean; plagiarism: boolean }
  files: { key: string; name: string; student: string; studentId: string; email: string; kind: Submission['fileKind']; text: string }[]
}

function safeName(n: string) {
  return (n.replace(/[^A-Za-z0-9._-]+/g, '_').replace(/^\.+/, '') || 'file').slice(0, 120)
}

api.post('/uploads', upload.any(), async (req, res) => {
  let meta: UploadMeta
  try { meta = JSON.parse(String(req.body?.meta ?? '')) } catch { res.status(400).json({ error: 'bad_request' }); return }
  const rubric = docGet(`rubrics/${meta.rubricId}`) as { name: string; assignment: string; totalPoints: number } | null
  if (!rubric) { res.status(400).json({ error: 'no_rubric', message: 'Pick a rubric first.' }); return }
  const files = new Map(((req.files as Express.Multer.File[]) ?? []).map(f => [f.fieldname, f]))
  const batchId = meta.batchId && /^b[A-Za-z0-9]{6,20}$/.test(meta.batchId) ? meta.batchId : newId('b')
  kvSet(`batchopen:${batchId}`, meta.final === false)
  const s = settings()
  const ids: string[] = []
  const toOcr: { id: string; file: string; kind: 'scan' | 'image' }[] = []
  for (const f of meta.files.slice(0, 500)) {
    const id = newId('s')
    const blob = files.get(`file_${f.key}`)
    let stored = ''
    if (blob) {
      const dir = path.join(config.dataDir, 'files', id)
      fs.mkdirSync(dir, { recursive: true })
      stored = path.join(dir, safeName(f.name))
      fs.writeFileSync(stored, blob.buffer)
    }
    const r = matchRoster(s.roster, { studentId: f.studentId, name: f.student, fileName: f.name })
    const text = String(f.text ?? '').slice(0, 200_000)
    const needsOcr = (f.kind === 'scan' || f.kind === 'image') && !text.trim()
    const now = Date.now()
    docSet(`submissions/${id}`, {
      student: r?.name ?? String(f.student || f.name), studentId: r?.studentId ?? String(f.studentId ?? ''), email: r?.email ?? String(f.email ?? ''),
      assignment: rubric.assignment, rubricId: meta.rubricId, rubricName: rubric.name, file: f.name, fileSize: blob?.size ?? text.length,
      fileKind: f.kind, content: '', score: null, total: rubric.totalPoints, aiScore: null, status: 'pending', gradedBy: '—', confidence: null,
      criteria: [], summary: '', flagReason: '', similarity: null, submittedAt: now, gradedAt: null, updatedAt: now, approvedBy: null,
      approvedAt: null, overridden: false, uploadedBy: req.user!.id, queueState: needsOcr ? 'ocr' : 'waiting', batchId,
      options: { flagLow: !!meta.options?.flagLow, detailed: meta.options?.detailed !== false, plagiarism: !!meta.options?.plagiarism },
      storedFile: stored ? path.relative(config.dataDir, stored) : '', error: '',
    })
    if (text) docSet(`submissionContent/${id}`, { text })
    if (needsOcr && stored) toOcr.push({ id, file: stored, kind: f.kind as 'scan' | 'image' })
    else if (needsOcr) docPatch(`submissions/${id}`, { status: 'error', queueState: null, error: 'The scanned file was not received.' })
    else enqueueGrade(id)
    ids.push(id)
  }
  res.json({ batchId, ids })
  if (meta.final !== false) checkBatch(batchId)

  for (const o of toOcr) {
    try {
      const text = await ocrFileAuto(o.file, o.kind)
      if (!text.replace(/--- Page \d+ ---/g, '').trim()) throw new Error('No readable text was found on the scanned pages.')
      console.log(`[OCR] Done ${o.id} (${path.basename(o.file)}): ${text.length} chars`)
      docSet(`submissionContent/${o.id}`, { text })
      enqueueGrade(o.id)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'OCR failed.'
      console.error(`[OCR] Failed ${o.id} (${path.basename(o.file)}): ${msg}`)
      docPatch(`submissions/${o.id}`, { status: 'error', queueState: null, error: msg, updatedAt: Date.now() })
    }
  }
})

api.get('/files/:id', (req, res) => {
  const sub = docGet(`submissions/${req.params.id}`) as Submission | null
  const inline = req.query.inline === '1' || req.query.inline === 'true'
  sendStoredFile(res, config.dataDir, sub, inline)
})

api.post('/submissions/:id/regrade', (req, res) => {
  const sub = docGet(`submissions/${req.params.id}`) as Submission | null
  if (!sub) { res.status(404).json({ error: 'not_found' }); return }
  if (sub.status === 'pending' && sub.queueState === 'grading') { res.status(409).json({ error: 'busy', message: 'This file is already being graded.' }); return }
  if (!docGet(`submissionContent/${req.params.id}`)) { res.status(400).json({ error: 'no_text', message: 'There is no readable text for this file. Upload it again.' }); return }
  const rubricId = req.body?.rubricId ? String(req.body.rubricId) : sub.rubricId
  if (rubricId !== sub.rubricId) {
    const r = docGet(`rubrics/${rubricId}`) as { name: string; totalPoints: number } | null
    if (!r) { res.status(400).json({ error: 'no_rubric' }); return }
    docPatch(`submissions/${req.params.id}`, { rubricId, rubricName: r.name, total: r.totalPoints })
  }
  enqueueGrade(req.params.id)
  res.json({ ok: true, model: modelStatus() })
})

api.post('/batches/:id/cancel', (req, res) => { res.json({ cancelled: cancelBatch(req.params.id) }) })

api.post('/rubrics/import', requireRole('admin', 'professor'), async (req, res) => {
  const text = String(req.body?.text ?? '').trim()
  if (!text) { res.status(400).json({ error: 'empty', message: 'No text found in that rubric file.' }); return }
  if (!modelStatus().online) { res.status(503).json({ error: 'model_offline', message: 'The grading model is offline, so it can’t read this rubric now. Start the Fir job, or upload a .json rubric.' }); return }
  try {
    res.json({ rubric: await importRubric(text, String(req.body?.assignment ?? settings().currentAssignment)) })
  } catch (e) {
    res.status(502).json({ error: 'model_failed', message: e instanceof Error ? e.message : 'The model could not read this rubric.' })
  }
})

/* ---- admin: danger zone ---- */
function deleteSubmission(id: string) {
  const sub = docGet(`submissions/${id}`) as Submission | null
  dropTasksFor(id)
  docDelete(`submissions/${id}`)
  docDelete(`submissionContent/${id}`)
  if (sub?.storedFile) fs.rmSync(path.join(config.dataDir, 'files', id), { recursive: true, force: true })
}

api.delete('/submissions/:id', requireRole('admin', 'professor'), (req, res) => { deleteSubmission(req.params.id); res.json({ ok: true }) })

api.post('/admin/reset', requireRole('admin'), (req, res) => {
  const assignment = String(req.body?.assignment ?? '')
  const subs = docList('submissions').filter(d => d.data.assignment === assignment)
  subs.forEach(s => deleteSubmission(s.id))
  logActivity('system', 'Grades reset', `All ${subs.length} submissions for ${assignment} were deleted.`, req.user!.id)
  res.json({ deleted: subs.length })
})

api.post('/admin/wipe', requireRole('admin'), (req, res) => {
  const subs = docList('submissions')
  subs.forEach(s => deleteSubmission(s.id))
  for (const col of ['rubrics', 'exports', 'activity']) for (const d of docList(col)) docDelete(`${col}/${d.id}`)
  db.prepare('DELETE FROM tasks').run()
  logActivity('system', 'Course data deleted', `${subs.length} submissions and all rubrics, exports and activity were deleted.`, req.user!.id)
  res.json({ deleted: subs.length })
})

/* ---- errors ---- */
api.use((err: Error & { code?: string }, _req: Request, res: Response, next: NextFunction) => {
  void next
  if (err.code === 'LIMIT_FILE_SIZE') { res.status(413).json({ error: 'too_large', message: `A file is over the ${config.maxUploadMb} MB limit.` }); return }
  console.error(err)
  res.status(500).json({ error: 'server_error', message: 'Something went wrong on the server.' })
})

/* ================= static site ================= */
if (fs.existsSync(config.staticDir)) {
  app.use(express.static(config.staticDir, { index: false, maxAge: '1h' }))
  app.get(/^(?!\/api\/).*/, (_req, res) => {
    res.setHeader('Cache-Control', 'no-cache')
    res.sendFile(path.join(config.staticDir, 'index.html'))
  })
}

startMaintenance()
app.listen(config.port, config.host, () => {
  console.log(`GradeAI listening on ${config.host}:${config.port} (public URL ${config.publicUrl})`)
  if (!config.workerToken) console.warn('WORKER_TOKEN is not set: the Fir worker cannot connect until you set it.')
  if (!ocrTools.tesseract) console.warn('tesseract not found: scanned submissions cannot be read.')
  if (userCount() === 0) console.log(`No accounts yet. Open ${config.publicUrl} to create the first administrator.`)
})

