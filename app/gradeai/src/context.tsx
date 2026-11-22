import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { HttpStore, newId, type DocEntry, type Store } from './lib/store'
import { api, ApiError, downloadFile } from './lib/api'
import { DEFAULT_SETTINGS } from './lib/defaults'
import type { Activity, ActivityType, CourseSettings, ExportRecord, Member, ModelStatus, Person, Role, Rubric, Rubric as R, Submission } from './lib/types'

export const ROLE_COLORS: Record<Role, string> = { professor: '#5b4fcf', ta: '#1e3765', admin: '#b45309' }
export const ROLE_LABELS: Record<Role, string> = { professor: 'Professor', ta: 'Teaching Assistant', admin: 'Administrator' }

export interface Toast { id: number; text: string; kind: 'ok' | 'warn' | 'error' }
export type AuthState = 'loading' | 'signedOut' | 'setup' | 'invite' | 'ready'

interface UploadFile { key: string; name: string; student: string; studentId: string; email: string; kind: Submission['fileKind']; text: string; blob?: Blob }

interface Ctx {
  auth: AuthState
  refreshAuth: () => Promise<void>
  signOut: () => Promise<void>
  ready: boolean
  offline: boolean
  me: Person
  actualRole: Role
  role: Role
  previewRole: Role | null
  setPreviewRole: (r: Role | null) => void
  isAdmin: boolean
  settings: CourseSettings
  rubrics: Rubric[]
  submissions: Submission[]
  activity: Activity[]
  exports: ExportRecord[]
  users: Member[]
  refreshUsers: () => Promise<void>
  model: ModelStatus
  ocr: { tesseract: boolean; pdftoppm: boolean; backend?: 'gemini' | 'tesseract' | 'none' }
  lastSeenActivity: number
  markActivitySeen: () => void
  toasts: Toast[]
  notify: (text: string, kind?: Toast['kind']) => void
  saveSettings: (patch: Partial<CourseSettings>) => Promise<void>
  saveRubric: (r: Rubric) => Promise<void>
  deleteRubric: (id: string) => Promise<void>
  saveSubmission: (s: Submission) => Promise<void>
  getContent: (id: string) => Promise<string>
  deleteSubmission: (id: string) => Promise<void>
  addExport: (e: Omit<ExportRecord, 'id'>) => Promise<void>
  logActivity: (type: ActivityType, title: string, body: string) => Promise<void>
  uploadBatch: (rubricId: string, options: { flagLow: boolean; detailed: boolean; plagiarism: boolean }, files: UploadFile[], onProgress?: (pct: number) => void) => Promise<{ batchId: string; ids: string[] }>
  regrade: (id: string) => Promise<void>
  cancelBatch: (batchId: string) => Promise<number>
  importRubric: (text: string, assignment: string) => Promise<Omit<R, 'id' | 'createdBy' | 'updatedAt' | 'version'>>
  download: typeof downloadFile
  resolvePeople: (ids: string[]) => Promise<Record<string, Person>>
}

const AppContext = createContext<Ctx | null>(null)

export function useApp() {
  const c = useContext(AppContext)
  if (!c) throw new Error('useApp outside provider')
  return c
}

const OFFLINE_MODEL: ModelStatus = { online: false, lastSeen: null, model: null, slurmJobId: null, node: null, endsAt: null, waiting: 0, grading: 0 }
const NOBODY: Person = { id: '', name: '', email: null, avatarUrl: null, color: '#6b7a99' }

function errMsg(e: unknown) {
  if (e instanceof ApiError) return e.message
  return 'Could not save. Check your connection and try again.'
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>('loading')
  const [store, setStore] = useState<Store | null>(null)
  const [me, setMe] = useState<Person>(NOBODY)
  const [actualRole, setActualRole] = useState<Role>('ta')
  const [previewRole, setPreviewRoleState] = useState<Role | null>(null)
  const [ocr, setOcr] = useState({ tesseract: false, pdftoppm: false })

  const [settingsDoc, setSettingsDoc] = useState<CourseSettings | null>(null)
  const [rubrics, setRubrics] = useState<Rubric[]>([])
  const [submissions, setSubmissions] = useState<Submission[]>([])
  const [activity, setActivity] = useState<Activity[]>([])
  const [exportsList, setExports] = useState<ExportRecord[]>([])
  const [users, setUsers] = useState<Member[]>([])
  const [model, setModel] = useState<ModelStatus>(OFFLINE_MODEL)
  const [lastSeenActivity, setLastSeen] = useState<number>(0)
  const [loaded, setLoaded] = useState({ settings: false, rubrics: false, submissions: false })
  const [offline, setOffline] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])

  const notify = useCallback((text: string, kind: Toast['kind'] = 'ok') => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, text, kind }])
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), kind === 'error' ? 6000 : 3500)
  }, [])

  /* ---- who is signed in ---- */
  const refreshAuth = useCallback(async () => {
    if (/^#invite=/.test(location.hash)) { setAuth('invite'); return }
    try {
      const r = await api<{ user: { id: string; email: string; name: string; role: Role } | null; ocr: typeof ocr }>('/me')
      if (!r.user) {
        const s = await api<{ needsSetup: boolean }>('/setup')
        setAuth(s.needsSetup ? 'setup' : 'signedOut')
        return
      }
      setMe({ id: r.user.id, name: r.user.name, email: r.user.email, avatarUrl: null, color: ROLE_COLORS[r.user.role] })
      setActualRole(r.user.role)
      setOcr(r.ocr)
      setAuth('ready')
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        try {
          const s = await api<{ needsSetup: boolean }>('/setup')
          setAuth(s.needsSetup ? 'setup' : 'signedOut')
        } catch { setAuth('signedOut') }
      } else {
        setAuth('signedOut')
      }
    }
  }, [])

  useEffect(() => { refreshAuth() }, [refreshAuth])

  const signOut = useCallback(async () => {
    try { await api('/logout', { method: 'POST' }) } catch { /* already out */ }
    store?.close()
    setStore(null)
    setLoaded({ settings: false, rubrics: false, submissions: false })
    setAuth('signedOut')
  }, [store])

  /* ---- open the live store once signed in ---- */
  useEffect(() => {
    if (auth !== 'ready') return
    const s = new HttpStore({
      onModel: setModel,
      onConnection: ok => setOffline(!ok),
      onSignedOut: () => { setStore(null); setAuth('signedOut') },
    })
    setStore(s)
    return () => s.close()
  }, [auth])

  const refreshUsers = useCallback(async () => {
    try { setUsers((await api<{ users: Member[] }>('/users')).users) } catch { /* keep last */ }
  }, [])

  useEffect(() => {
    if (!store) return
    const asList = <T,>(docs: DocEntry[]) => docs.map(d => ({ ...(d.data as T), id: d.id }))
    refreshUsers()
    const unsubs = [
      store.subscribeDoc('settings/course', d => {
        setSettingsDoc(d ? ({ ...DEFAULT_SETTINGS, ...d } as CourseSettings) : null)
        setLoaded(l => ({ ...l, settings: true }))
      }, () => setLoaded(l => ({ ...l, settings: true }))),
      store.subscribeCollection('rubrics', docs => {
        setRubrics(asList<Rubric>(docs).sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0)))
        setLoaded(l => ({ ...l, rubrics: true }))
      }, () => setLoaded(l => ({ ...l, rubrics: true }))),
      store.subscribeCollection('submissions', docs => {
        setSubmissions(asList<Submission>(docs))
        setLoaded(l => ({ ...l, submissions: true }))
      }, () => setLoaded(l => ({ ...l, submissions: true }))),
      store.subscribeCollection('activity', docs => setActivity(asList<Activity>(docs).sort((a, b) => b.at - a.at))),
      store.subscribeCollection('exports', docs => setExports(asList<ExportRecord>(docs).sort((a, b) => b.at - a.at))),
    ]
    api<ModelStatus>('/model').then(setModel).catch(() => undefined)
    return () => unsubs.forEach(u => u())
  }, [store, refreshUsers])

  const statePath = me.id ? `data/users/${me.id}/state` : null
  useEffect(() => {
    if (!store || !statePath) return
    return store.subscribeDoc(statePath, d => setLastSeen(Number(d?.lastSeenActivity ?? 0)))
  }, [store, statePath])

  const settings = settingsDoc ?? DEFAULT_SETTINGS
  const isAdmin = actualRole === 'admin'
  const role: Role = isAdmin ? (previewRole ?? actualRole) : actualRole
  const setPreviewRole = useCallback((r: Role | null) => setPreviewRoleState(r && r === actualRole ? null : r), [actualRole])

  const guard = useCallback(async (fn: () => Promise<void>) => {
    if (!store) return
    try { await fn() } catch (e) { notify(errMsg(e), 'error'); throw e }
  }, [store, notify])

  const saveSettings = useCallback(async (patch: Partial<CourseSettings>) => {
    await guard(() => store!.set('settings/course', { ...settings, ...patch, updatedAt: Date.now() }))
  }, [guard, store, settings])

  const logActivity = useCallback(async (type: ActivityType, title: string, body: string) => {
    if (!store) return
    try { await store.set(`activity/${newId('ev')}`, { type, title, body, at: Date.now(), by: me.id }) } catch { /* best-effort */ }
  }, [store, me.id])

  const saveRubric = useCallback(async (r: Rubric) => {
    const { id, ...rest } = r
    await guard(() => store!.set(`rubrics/${id}`, rest))
  }, [guard, store])

  const deleteRubric = useCallback(async (id: string) => { await guard(() => store!.remove(`rubrics/${id}`)) }, [guard, store])

  const saveSubmission = useCallback(async (s: Submission) => {
    const { id, ...rest } = s
    await guard(() => store!.set(`submissions/${id}`, { ...rest, content: '', updatedAt: Date.now() }))
  }, [guard, store])

  const getContent = useCallback(async (id: string) => {
    if (!store) return ''
    const d = await store.get(`submissionContent/${id}`)
    return String(d?.text ?? '')
  }, [store])

  const deleteSubmission = useCallback(async (id: string) => {
    await guard(async () => { await api(`/submissions/${encodeURIComponent(id)}`, { method: 'DELETE' }) })
  }, [guard])

  const addExport = useCallback(async (e: Omit<ExportRecord, 'id'>) => {
    await guard(() => store!.set(`exports/${newId('ex')}`, e))
  }, [guard, store])

  const uploadBatch = useCallback(async (rubricId: string, options: { flagLow: boolean; detailed: boolean; plagiarism: boolean }, files: UploadFile[], onProgress?: (pct: number) => void) => {
    // Send in chunks so one huge batch doesn't hit request limits, and so progress is visible.
    const CHUNK = 25
    let batchId = ''
    const ids: string[] = []
    for (let i = 0; i < files.length; i += CHUNK) {
      const part = files.slice(i, i + CHUNK)
      const form = new FormData()
      const final = i + CHUNK >= files.length
      form.append('meta', JSON.stringify({ rubricId, options, batchId: batchId || undefined, final, files: part.map(({ blob: _b, ...f }) => { void _b; return f }) }))
      for (const f of part) if (f.blob) form.append(`file_${f.key}`, f.blob, f.name)
      const r = await api<{ batchId: string; ids: string[] }>('/uploads', { form })
      batchId = r.batchId
      ids.push(...r.ids)
      onProgress?.(Math.round(((i + part.length) / files.length) * 100))
    }
    return { batchId, ids }
  }, [])

  const regrade = useCallback(async (id: string) => {
    await guard(async () => { await api(`/submissions/${encodeURIComponent(id)}/regrade`, { method: 'POST', body: {} }) })
  }, [guard])

  const cancelBatch = useCallback(async (batchId: string) => {
    const r = await api<{ cancelled: number }>(`/batches/${encodeURIComponent(batchId)}/cancel`, { method: 'POST', body: {} })
    return r.cancelled
  }, [])

  const importRubric = useCallback(async (text: string, assignment: string) => {
    const r = await api<{ rubric: Omit<R, 'id' | 'createdBy' | 'updatedAt' | 'version'> }>('/rubrics/import', { body: { text, assignment } })
    return r.rubric
  }, [])

  const markActivitySeen = useCallback(() => {
    if (!store || !statePath) return
    const newest = activity[0]?.at ?? 0
    if (newest <= lastSeenActivity) return
    setLastSeen(newest)
    store.set(statePath, { lastSeenActivity: newest }).catch(() => undefined)
  }, [store, statePath, activity, lastSeenActivity])

  const resolvePeople = useCallback(async (ids: string[]) => {
    const out: Record<string, Person> = {}
    for (const id of ids) {
      const u = users.find(x => x.id === id)
      out[id] = u
        ? { id, name: u.name, email: u.email, avatarUrl: null, color: ROLE_COLORS[u.role] }
        : { id, name: id === 'system' ? 'GradeAI' : '', email: null, avatarUrl: null, color: '#6b7a99' }
    }
    return out
  }, [users])

  const ready = !!store && loaded.settings && loaded.rubrics && loaded.submissions

  const value: Ctx = useMemo(() => ({
    auth, refreshAuth, signOut, ready, offline, me, actualRole, role, previewRole, setPreviewRole, isAdmin,
    settings, rubrics, submissions, activity, exports: exportsList, users, refreshUsers, model, ocr,
    lastSeenActivity, markActivitySeen, toasts, notify,
    saveSettings, saveRubric, deleteRubric, saveSubmission, getContent, deleteSubmission, addExport, logActivity,
    uploadBatch, regrade, cancelBatch, importRubric, download: downloadFile, resolvePeople,
  }), [auth, refreshAuth, signOut, ready, offline, me, actualRole, role, previewRole, setPreviewRole, isAdmin, settings, rubrics, submissions, activity, exportsList, users, refreshUsers, model, ocr, lastSeenActivity, markActivitySeen, toasts, notify, saveSettings, saveRubric, deleteRubric, saveSubmission, getContent, deleteSubmission, addExport, logActivity, uploadBatch, regrade, cancelBatch, importRubric, resolvePeople])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

/** Resolve display names for user ids. */
export function usePeople(ids: string[]) {
  const { resolvePeople } = useApp()
  const key = [...new Set(ids.filter(Boolean))].sort().join('|')
  const [map, setMap] = useState<Record<string, Person>>({})
  useEffect(() => {
    let live = true
    resolvePeople(key ? key.split('|') : []).then(m => { if (live) setMap(m) })
    return () => { live = false }
  }, [key, resolvePeople])
  return map
}

export function personName(map: Record<string, Person>, id: string | null | undefined, fallback = 'Someone') {
  if (!id) return '—'
  if (id === 'AI') return 'AI'
  return map[id]?.name || fallback
}

/** What the current (possibly previewed) role may do. The server enforces the real role. */
export function usePerms() {
  const { role, isAdmin, previewRole } = useApp()
  const staff = role === 'professor' || role === 'admin'
  return {
    canGrade: true,
    canEditRubrics: staff,
    canExport: staff,
    canEditSettings: staff,
    canManageTeam: isAdmin && previewRole === null,
    canDanger: role === 'admin',
    canApprove: true,
  }
}
