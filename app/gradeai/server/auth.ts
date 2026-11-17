import crypto from 'node:crypto'
import type { NextFunction, Request, Response } from 'express'
import { config } from './config'
import { db } from './db'

export type Role = 'admin' | 'professor' | 'ta'
export interface User { id: string; email: string; name: string; role: Role }

declare module 'express-serve-static-core' {
  interface Request { user?: User }
}

const COOKIE = 'gradeai_session'

export function newId(prefix = '') {
  return prefix + crypto.randomBytes(9).toString('base64url').replace(/[^A-Za-z0-9]/g, '').slice(0, 14)
}

const sha256 = (s: string) => crypto.createHash('sha256').update(s).digest('hex')

export function hashPassword(pw: string): string {
  const salt = crypto.randomBytes(16)
  const key = crypto.scryptSync(pw, salt, 64, { N: 16384, r: 8, p: 1 })
  return `scrypt$${salt.toString('base64')}$${key.toString('base64')}`
}

export function verifyPassword(pw: string, stored: string | null): boolean {
  if (!stored) return false
  const [alg, saltB64, keyB64] = stored.split('$')
  if (alg !== 'scrypt' || !saltB64 || !keyB64) return false
  const key = Buffer.from(keyB64, 'base64')
  const test = crypto.scryptSync(pw, Buffer.from(saltB64, 'base64'), key.length, { N: 16384, r: 8, p: 1 })
  return crypto.timingSafeEqual(key, test)
}

export function passwordProblem(pw: unknown): string | null {
  if (typeof pw !== 'string' || pw.length < 10) return 'Use at least 10 characters.'
  if (pw.length > 200) return 'That password is too long.'
  return null
}

export function createSession(res: Response, userId: string) {
  const token = crypto.randomBytes(32).toString('base64url')
  const expires = Date.now() + config.sessionDays * 864e5
  db.prepare('INSERT INTO sessions (token_hash, user_id, expires) VALUES (?, ?, ?)').run(sha256(token), userId, expires)
  db.prepare('UPDATE users SET last_login = ? WHERE id = ?').run(Date.now(), userId)
  res.cookie(COOKIE, token, { httpOnly: true, sameSite: 'lax', secure: config.cookieSecure, expires: new Date(expires), path: '/' })
}

export function destroySession(req: Request, res: Response) {
  const token = readCookie(req)
  if (token) db.prepare('DELETE FROM sessions WHERE token_hash = ?').run(sha256(token))
  res.clearCookie(COOKIE, { path: '/' })
}

function readCookie(req: Request): string | null {
  const raw = req.headers.cookie
  if (!raw) return null
  for (const part of raw.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k === COOKIE) return decodeURIComponent(v.join('='))
  }
  return null
}

export function loadUser(req: Request, _res: Response, next: NextFunction) {
  const token = readCookie(req)
  if (token) {
    const row = db.prepare(
      `SELECT u.id, u.email, u.name, u.role, s.expires FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?`,
    ).get(sha256(token)) as (User & { expires: number }) | undefined
    if (row && row.expires > Date.now()) req.user = { id: row.id, email: row.email, name: row.name, role: row.role }
  }
  next()
}

export function requireUser(req: Request, res: Response, next: NextFunction) {
  if (!req.user) { res.status(401).json({ error: 'signed_out' }); return }
  next()
}

export function requireRole(...roles: Role[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) { res.status(401).json({ error: 'signed_out' }); return }
    if (!roles.includes(req.user.role)) { res.status(403).json({ error: 'forbidden', message: 'Your role cannot do this.' }); return }
    next()
  }
}

/** Mutating browser requests must carry this header: a cross-site form cannot set it (CSRF guard). */
export function requireAppHeader(req: Request, res: Response, next: NextFunction) {
  if (req.method !== 'GET' && req.method !== 'HEAD' && req.headers['x-gradeai'] !== '1') {
    res.status(400).json({ error: 'bad_request', message: 'Missing X-GradeAI header.' })
    return
  }
  next()
}

/* ---- invites ---- */

export function makeInvite(userId: string, days = 7) {
  const token = crypto.randomBytes(24).toString('base64url')
  db.prepare('UPDATE users SET invite_hash = ?, invite_expires = ? WHERE id = ?').run(sha256(token), Date.now() + days * 864e5, userId)
  return `${config.publicUrl}/#invite=${token}`
}

export function findInvite(token: string) {
  return db.prepare('SELECT id, email, name, role, invite_expires FROM users WHERE invite_hash = ?').get(sha256(token)) as
    (User & { invite_expires: number }) | undefined
}

/* ---- naive login throttling ---- */
const attempts = new Map<string, { n: number; until: number }>()
export function throttled(key: string) {
  const a = attempts.get(key)
  return !!a && a.n >= 8 && a.until > Date.now()
}
export function noteFailure(key: string) {
  const a = attempts.get(key) ?? { n: 0, until: 0 }
  a.n += 1
  a.until = Date.now() + 10 * 60_000
  attempts.set(key, a)
}
export function clearFailures(key: string) { attempts.delete(key) }

export function workerAuth(req: Request, res: Response, next: NextFunction) {
  const h = req.headers.authorization || ''
  const token = h.startsWith('Bearer ') ? h.slice(7) : ''
  if (!config.workerToken) { res.status(503).json({ error: 'worker_disabled', message: 'Set WORKER_TOKEN on the server.' }); return }
  const a = Buffer.from(token)
  const b = Buffer.from(config.workerToken)
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) { res.status(401).json({ error: 'bad_token' }); return }
  next()
}
