/* Live document store backed by the GradeAI server: REST for reads/writes, Server-Sent Events for changes
   made by anyone on the team (and by the grading worker). */
import { api } from './api'
import type { ModelStatus } from './types'

/* eslint-disable @typescript-eslint/no-explicit-any */
export type DocData = Record<string, any>
export interface DocEntry { id: string; data: DocData }

export interface Store {
  subscribeCollection(path: string, next: (docs: DocEntry[], confirmed: boolean) => void, onError?: (code: string) => void): () => void
  subscribeDoc(path: string, next: (data: DocData | null, confirmed: boolean) => void, onError?: (code: string) => void): () => void
  get(path: string): Promise<DocData | null>
  set(path: string, data: DocData): Promise<void>
  remove(path: string): Promise<void>
  close(): void
}

const parentOf = (p: string) => p.slice(0, p.lastIndexOf('/'))
const q = encodeURIComponent

export class HttpStore implements Store {
  private cols = new Map<string, Map<string, DocData>>()
  private colListeners = new Map<string, Set<(docs: DocEntry[], c: boolean) => void>>()
  private docListeners = new Map<string, Set<(d: DocData | null, c: boolean) => void>>()
  private es: EventSource | null = null
  private hadError = false

  constructor(private hooks: { onModel: (m: ModelStatus) => void; onConnection: (ok: boolean) => void; onSignedOut: () => void }) {
    this.connect()
  }

  private connect() {
    const es = new EventSource('/api/events', { withCredentials: true })
    this.es = es
    es.addEventListener('open', () => {
      this.hooks.onConnection(true)
      if (this.hadError) { this.hadError = false; this.refetchAll() }
    })
    es.addEventListener('error', () => {
      this.hadError = true
      this.hooks.onConnection(false)
      if (es.readyState === EventSource.CLOSED) {
        // The server ended the stream (e.g. signed out); check, then reconnect.
        api<{ user: unknown }>('/me').then(r => (r.user ? setTimeout(() => this.connect(), 2000) : this.hooks.onSignedOut())).catch(() => setTimeout(() => this.connect(), 5000))
      }
    })
    es.addEventListener('model', e => { try { this.hooks.onModel(JSON.parse((e as MessageEvent).data)) } catch { /* ignore */ } })
    es.addEventListener('doc', e => {
      try {
        const { path, op, data } = JSON.parse((e as MessageEvent).data) as { path: string; op: 'set' | 'delete'; data?: DocData }
        this.apply(path, op, data)
      } catch { /* ignore */ }
    })
  }

  close() { this.es?.close(); this.es = null }

  private emitCol(col: string) {
    const m = this.cols.get(col)
    if (!m) return
    const list = [...m.entries()].map(([id, data]) => ({ id, data })).sort((a, b) => a.id.localeCompare(b.id))
    this.colListeners.get(col)?.forEach(fn => fn(list, true))
  }

  private apply(path: string, op: 'set' | 'delete', data?: DocData) {
    const col = parentOf(path)
    const id = path.slice(col.length + 1)
    const m = this.cols.get(col)
    if (m) {
      if (op === 'delete') m.delete(id)
      else if (data) m.set(id, data)
      this.emitCol(col)
    }
    const ls = this.docListeners.get(path)
    if (ls?.size) {
      if (op === 'delete') ls.forEach(fn => fn(null, true))
      else if (data) ls.forEach(fn => fn(data, true))
      else this.get(path).then(d => ls.forEach(fn => fn(d, true))).catch(() => undefined)
    }
  }

  private async loadCol(col: string) {
    const r = await api<{ docs: DocEntry[] }>(`/docs?col=${q(col)}`)
    this.cols.set(col, new Map(r.docs.map(d => [d.id, d.data])))
    this.emitCol(col)
  }

  private refetchAll() {
    for (const col of this.colListeners.keys()) this.loadCol(col).catch(() => undefined)
    for (const [path, ls] of this.docListeners) this.get(path).then(d => ls.forEach(fn => fn(d, true))).catch(() => undefined)
  }

  subscribeCollection(path: string, next: (docs: DocEntry[], confirmed: boolean) => void, onError?: (code: string) => void) {
    if (!this.colListeners.has(path)) this.colListeners.set(path, new Set())
    this.colListeners.get(path)!.add(next)
    if (this.cols.has(path)) queueMicrotask(() => this.emitCol(path))
    else this.loadCol(path).catch(e => onError?.(e?.code ?? 'unavailable'))
    return () => { this.colListeners.get(path)?.delete(next) }
  }

  subscribeDoc(path: string, next: (data: DocData | null, confirmed: boolean) => void, onError?: (code: string) => void) {
    if (!this.docListeners.has(path)) this.docListeners.set(path, new Set())
    this.docListeners.get(path)!.add(next)
    this.get(path).then(d => next(d, true)).catch(e => onError?.(e?.code ?? 'unavailable'))
    return () => { this.docListeners.get(path)?.delete(next) }
  }

  async get(path: string) {
    const r = await api<{ data: DocData | null }>(`/doc?path=${q(path)}`)
    return r.data
  }

  async set(path: string, data: DocData) {
    const clean = JSON.parse(JSON.stringify(data))
    await api(`/doc?path=${q(path)}`, { method: 'PUT', body: { data: clean } })
    // The server echoes every change over the event stream; apply locally only if that stream is down.
    if (this.hadError) this.apply(path, 'set', clean)
  }

  async remove(path: string) {
    await api(`/doc?path=${q(path)}`, { method: 'DELETE' })
    if (this.hadError) this.apply(path, 'delete')
  }
}

export function newId(prefix = '') {
  const r = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID().replace(/-/g, '').slice(0, 16) : Math.random().toString(36).slice(2, 14)
  return prefix + r
}
