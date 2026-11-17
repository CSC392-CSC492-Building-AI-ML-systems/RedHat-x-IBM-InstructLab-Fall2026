import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useApp, ROLE_LABELS } from '../context'
import { api, ApiError } from '../lib/api'
import type { Role } from '../lib/types'
import { Button, Notice, Spinner } from './ui'

function Shell({ title, sub, children }: { title: string; sub: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-full flex items-center justify-center p-4" style={{ background: 'var(--card)' }}>
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-8 h-8 rounded flex items-center justify-center text-xs font-bold" style={{ background: 'var(--primary)', color: '#fff' }}>AI</div>
          <div className="text-lg tracking-tight">GradeAI</div>
        </div>
        <div className="rounded p-6" style={{ background: 'var(--background)', border: '1px solid var(--border)', boxShadow: '0 8px 32px rgba(30,55,101,0.06)' }}>
          <h1 className="text-lg tracking-tight mb-1">{title}</h1>
          <p className="text-xs leading-relaxed mb-5" style={{ color: 'var(--muted-foreground)' }}>{sub}</p>
          {children}
        </div>
      </div>
    </div>
  )
}

function Field({ id, label, type = 'text', value, onChange, autoComplete, disabled }: { id: string; label: string; type?: string; value: string; onChange: (v: string) => void; autoComplete?: string; disabled?: boolean }) {
  return (
    <div className="mb-3">
      <label htmlFor={id} className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        disabled={disabled}
        autoComplete={autoComplete}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm rounded outline-none"
        style={{ background: disabled ? 'var(--secondary)' : 'var(--muted)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
      />
    </div>
  )
}

function useSubmit(fn: () => Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try { await fn() } catch (err) { setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.') } finally { setBusy(false) }
  }
  return { busy, error, onSubmit }
}

export function SignIn() {
  const { refreshAuth } = useApp()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, onSubmit } = useSubmit(async () => {
    await api('/login', { body: { email, password } })
    await refreshAuth()
  })
  return (
    <Shell title="Sign in" sub="Use the email your course admin invited.">
      <form onSubmit={onSubmit}>
        <Field id="email" label="Email" type="email" value={email} onChange={setEmail} autoComplete="username" />
        <Field id="password" label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        {error && <Notice kind="error" className="mb-3">{error}</Notice>}
        <Button className="w-full" disabled={busy || !email || !password} onClick={() => undefined} type="submit">
          {busy ? <Spinner light size={14} /> : 'Sign in'}
        </Button>
      </form>
      <p className="text-[11px] mt-4 leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>Forgot your password? Ask a GradeAI administrator for a new sign-in link.</p>
    </Shell>
  )
}

export function FirstRun() {
  const { refreshAuth } = useApp()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { busy, error, onSubmit } = useSubmit(async () => {
    await api('/setup', { body: { name, email, password } })
    await refreshAuth()
  })
  return (
    <Shell title="Set up GradeAI" sub="Create the first administrator account. You can invite professors and TAs from Settings afterwards.">
      <form onSubmit={onSubmit}>
        <Field id="name" label="Your name" value={name} onChange={setName} autoComplete="name" />
        <Field id="email" label="Email" type="email" value={email} onChange={setEmail} autoComplete="username" />
        <Field id="password" label="Password (10+ characters)" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
        {error && <Notice kind="error" className="mb-3">{error}</Notice>}
        <Button className="w-full" type="submit" disabled={busy || !name || !email || password.length < 10}>
          {busy ? <Spinner light size={14} /> : 'Create administrator'}
        </Button>
      </form>
    </Shell>
  )
}

export function AcceptInvite() {
  const { refreshAuth } = useApp()
  const token = location.hash.replace(/^#invite=/, '')
  const [info, setInfo] = useState<{ name: string; email: string; role: Role } | null>(null)
  const [loadError, setLoadError] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')

  useEffect(() => {
    api<{ name: string; email: string; role: Role }>(`/invite/${encodeURIComponent(token)}`)
      .then(setInfo)
      .catch(e => setLoadError(e instanceof ApiError ? e.message : 'This link is not valid.'))
  }, [token])

  const { busy, error, onSubmit } = useSubmit(async () => {
    if (password !== confirm) throw new ApiError(400, 'mismatch', 'The two passwords don’t match.')
    await api(`/invite/${encodeURIComponent(token)}`, { body: { password } })
    history.replaceState(null, '', location.pathname + location.search)
    await refreshAuth()
  })

  if (loadError) {
    return (
      <Shell title="Link expired" sub={loadError}>
        <Button kind="secondary" className="w-full" onClick={() => { history.replaceState(null, '', location.pathname); refreshAuth() }}>Go to sign in</Button>
      </Shell>
    )
  }
  if (!info) return <Shell title="Opening your invite…" sub=""><Spinner /></Shell>

  return (
    <Shell title={`Welcome, ${info.name.split(' ')[0]}`} sub={`You've been added to GradeAI as ${ROLE_LABELS[info.role]}. Choose a password to finish.`}>
      <form onSubmit={onSubmit}>
        <Field id="email" label="Email" value={info.email} onChange={() => undefined} disabled />
        <Field id="password" label="Password (10+ characters)" type="password" value={password} onChange={setPassword} autoComplete="new-password" />
        <Field id="confirm" label="Confirm password" type="password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
        {error && <Notice kind="error" className="mb-3">{error}</Notice>}
        <Button className="w-full" type="submit" disabled={busy || password.length < 10}>
          {busy ? <Spinner light size={14} /> : 'Set password and continue'}
        </Button>
      </form>
    </Shell>
  )
}
