import { Router } from 'express'
import { STAFF } from './config'
import { db } from './db'
import { broadcastDoc } from './events'
import type { User } from './auth'

/* A small document store (path -> JSON), with the same path shape the frontend uses:
   collection/doc, collection/doc/subcollection/doc. Access is decided per collection by role. */

const SEG = /^[A-Za-z0-9_\-.~:@+]{1,200}$/

export function validPath(path: string, wantDoc: boolean) {
  const parts = path.split('/')
  if (!parts.length || parts.length > 16 || path.length > 1000) return false
  if (!parts.every(p => SEG.test(p) && p !== '.' && p !== '..')) return false
  return wantDoc ? parts.length % 2 === 0 : parts.length % 2 === 1
}

const parentOf = (path: string) => path.slice(0, path.lastIndexOf('/'))

export interface DocRow { path: string; data: Record<string, unknown>; updatedAt: number }

export function docGet(path: string): Record<string, unknown> | null {
  const r = db.prepare('SELECT data FROM docs WHERE path = ?').get(path) as { data: string } | undefined
  return r ? JSON.parse(r.data) : null
}

export function docSet(path: string, data: Record<string, unknown>) {
  const now = Date.now()
  db.prepare(
    'INSERT INTO docs (path, col, data, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at',
  ).run(path, parentOf(path), JSON.stringify(data), now)
  broadcastDoc(path, 'set', data)
}

export function docPatch(path: string, patch: Record<string, unknown>) {
  const cur = docGet(path)
  if (!cur) return null
  const next = { ...cur, ...patch }
  docSet(path, next)
  return next
}

export function docDelete(path: string) {
  db.prepare('DELETE FROM docs WHERE path = ?').run(path)
  broadcastDoc(path, 'delete')
}

export function docList(col: string): { id: string; data: Record<string, unknown> }[] {
  const rows = db.prepare('SELECT path, data FROM docs WHERE col = ? ORDER BY path').all(col) as { path: string; data: string }[]
  return rows.map(r => ({ id: r.path.slice(col.length + 1), data: JSON.parse(r.data) }))
}

/* ---- access rules ---- */

type Who = 'any' | 'staff' | 'admin' | 'none'
const RULES: Record<string, { read: Who; create: Who; update: Who; delete: Who }> = {
  settings: { read: 'any', create: 'staff', update: 'staff', delete: 'none' },
  rubrics: { read: 'any', create: 'staff', update: 'staff', delete: 'staff' },
  submissions: { read: 'any', create: 'none', update: 'any', delete: 'staff' },
  submissionContent: { read: 'any', create: 'none', update: 'none', delete: 'staff' },
  activity: { read: 'any', create: 'any', update: 'admin', delete: 'admin' },
  exports: { read: 'any', create: 'staff', update: 'staff', delete: 'admin' },
}

function allowed(who: Who, u: User) {
  if (who === 'any') return true
  if (who === 'staff') return STAFF.has(u.role)
  if (who === 'admin') return u.role === 'admin'
  return false
}

function ruleFor(path: string) {
  const own = path.match(/^data\/users\/([^/]+)\//)
  if (own) return { own: own[1] }
  return { rule: RULES[path.split('/')[0]] }
}

function canRead(u: User, path: string) {
  const r = ruleFor(path)
  if ('own' in r) return r.own === u.id
  return !!r.rule && allowed(r.rule.read, u)
}

/** Fields only the server sets on a submission; a browser write keeps the stored values. */
const SERVER_FIELDS = ['storedFile', 'batchId', 'options', 'model', 'queueState', 'uploadedBy', 'submittedAt', 'aiScore', 'fileKind', 'fileSize', 'file', 'confidence', 'gradedAt']

export function docsRouter() {
  const r = Router()

  r.get('/docs', (req, res) => {
    const col = String(req.query.col ?? '')
    if (!validPath(col, false)) { res.status(400).json({ error: 'bad_path' }); return }
    if (!canRead(req.user!, col + '/x')) { res.json({ docs: [] }); return }
    res.json({ docs: docList(col) })
  })

  r.get('/doc', (req, res) => {
    const path = String(req.query.path ?? '')
    if (!validPath(path, true)) { res.status(400).json({ error: 'bad_path' }); return }
    if (!canRead(req.user!, path)) { res.json({ data: null }); return }
    res.json({ data: docGet(path) })
  })

  r.put('/doc', (req, res) => {
    const path = String(req.query.path ?? '')
    const data = req.body?.data
    if (!validPath(path, true) || !data || typeof data !== 'object' || Array.isArray(data)) { res.status(400).json({ error: 'bad_request' }); return }
    const u = req.user!
    const existing = docGet(path)
    const r0 = ruleFor(path)
    if ('own' in r0) {
      if (r0.own !== u.id) { res.status(403).json({ error: 'forbidden' }); return }
    } else {
      const rule = r0.rule
      if (!rule || !allowed(existing ? rule.update : rule.create, u)) { res.status(403).json({ error: 'forbidden', message: 'Your role cannot change this.' }); return }
    }
    let next = data as Record<string, unknown>
    if (path.startsWith('submissions/') && existing) {
      if (existing.status === 'pending' && existing.queueState === 'grading') {
        res.status(409).json({ error: 'busy', message: 'This file is being graded right now. Try again in a moment.' })
        return
      }
      next = { ...next }
      for (const k of SERVER_FIELDS) if (k in existing) next[k] = existing[k]
    }
    if (JSON.stringify(next).length > 2_000_000) { res.status(413).json({ error: 'too_large' }); return }
    docSet(path, next)
    res.json({ ok: true })
  })

  r.delete('/doc', (req, res) => {
    const path = String(req.query.path ?? '')
    if (!validPath(path, true)) { res.status(400).json({ error: 'bad_path' }); return }
    const r0 = ruleFor(path)
    const u = req.user!
    const ok = 'own' in r0 ? r0.own === u.id : !!r0.rule && allowed(r0.rule.delete, u)
    if (!ok) { res.status(403).json({ error: 'forbidden', message: 'Your role cannot delete this.' }); return }
    docDelete(path)
    res.json({ ok: true })
  })

  return r
}
