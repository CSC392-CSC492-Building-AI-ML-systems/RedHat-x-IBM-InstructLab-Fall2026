import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import { useApp } from '../context'
import { initials } from '../lib/format'

export function PageHeader({ eyebrow, title, sub, actions }: { eyebrow: ReactNode; title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        <div className="mono text-xs tracking-widest uppercase mb-1" style={{ color: 'var(--muted-foreground)' }}>{eyebrow}</div>
        <h1 className="text-2xl tracking-tight" style={{ color: 'var(--foreground)' }}>{title}</h1>
        {sub && <p className="text-sm mt-1" style={{ color: 'var(--muted-foreground)' }}>{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2 shrink-0">{actions}</div>}
    </div>
  )
}

export function Card({ children, className = '', style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <div className={`rounded ${className}`} style={{ background: 'var(--card)', border: '1px solid var(--border)', ...style }}>
      {children}
    </div>
  )
}

export function Label({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`mono text-[10px] uppercase tracking-widest ${className}`} style={{ color: 'var(--muted-foreground)' }}>{children}</div>
}

type BtnKind = 'primary' | 'secondary' | 'danger' | 'ghost' | 'dashed'

const BTN: Record<BtnKind, CSSProperties> = {
  primary: { background: 'var(--primary)', color: 'var(--primary-foreground)' },
  secondary: { background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' },
  danger: { background: 'rgba(239,68,68,0.08)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' },
  ghost: { background: 'transparent', color: 'var(--muted-foreground)' },
  dashed: { background: 'transparent', color: 'var(--muted-foreground)', border: '1px dashed var(--border)' },
}

export function Button({ kind = 'primary', size = 'md', children, className = '', style, ...rest }: {
  kind?: BtnKind
  size?: 'sm' | 'md' | 'lg'
  children: ReactNode
  className?: string
  style?: CSSProperties
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const pad = size === 'sm' ? 'px-3 py-1.5 text-xs' : size === 'lg' ? 'px-4 py-3 text-sm' : 'px-4 py-2 text-sm'
  return (
    <button
      type="button"
      className={`${pad} rounded inline-flex items-center justify-center gap-2 transition-all duration-150 hover:opacity-90 ${className}`}
      style={{ ...BTN[kind], ...style }}
      {...rest}
    >
      {children}
    </button>
  )
}

export function Badge({ color, bg, children }: { color: string; bg: string; children: ReactNode }) {
  return <span className="mono text-[10px] px-2 py-0.5 rounded whitespace-nowrap" style={{ background: bg, color }}>{children}</span>
}

export const STATUS_BADGE = {
  graded: { label: 'Graded', bg: 'rgba(34,197,94,0.12)', color: '#16a34a' },
  review: { label: 'Needs Review', bg: 'rgba(245,158,11,0.12)', color: '#d97706' },
  pending: { label: 'Pending', bg: 'rgba(107,114,145,0.12)', color: 'var(--muted-foreground)' },
  error: { label: 'Failed', bg: 'rgba(239,68,68,0.1)', color: '#ef4444' },
} as const

export function StatusBadge({ status, short }: { status: keyof typeof STATUS_BADGE; short?: boolean }) {
  const s = STATUS_BADGE[status]
  return <Badge bg={s.bg} color={s.color}>{short && status === 'review' ? 'Review' : s.label}</Badge>
}

export function Notice({ kind = 'warn', children, className = '' }: { kind?: 'warn' | 'ok' | 'info' | 'error'; children: ReactNode; className?: string }) {
  const s = {
    warn: { background: 'rgba(245,158,11,0.08)', color: '#b45309', border: '1px solid rgba(245,158,11,0.25)' },
    ok: { background: 'rgba(34,197,94,0.08)', color: '#15803d', border: '1px solid rgba(34,197,94,0.25)' },
    info: { background: 'var(--secondary)', color: 'var(--secondary-foreground)', border: '1px solid var(--border)' },
    error: { background: 'rgba(239,68,68,0.06)', color: '#dc2626', border: '1px solid rgba(239,68,68,0.2)' },
  }[kind]
  return <div className={`rounded px-4 py-2.5 text-xs leading-relaxed ${className}`} style={s}>{children}</div>
}

export function Avatar({ name, color, url, size = 32 }: { name: string; color: string; url?: string | null; size?: number }) {
  if (url) return <img src={url} alt="" width={size} height={size} className="rounded-full shrink-0 object-cover" style={{ width: size, height: size }} />
  return (
    <div
      className="rounded-full flex items-center justify-center shrink-0 font-bold"
      style={{ width: size, height: size, background: color, color: '#fff', fontSize: Math.max(9, Math.round(size * 0.36)) }}
      aria-hidden
    >
      {initials(name || '?')}
    </div>
  )
}

export function Modal({ open, onClose, title, sub, children, width = 640, footer }: {
  open: boolean
  onClose: () => void
  title: ReactNode
  sub?: ReactNode
  children: ReactNode
  width?: number
  footer?: ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" style={{ background: 'rgba(13,20,40,0.35)' }} onMouseDown={onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        className="rounded w-full flex flex-col outline-none"
        style={{ maxWidth: width, maxHeight: 'calc(100% - 32px)', background: 'var(--background)', border: '1px solid var(--border)', boxShadow: '0 16px 48px rgba(30,55,101,0.18)' }}
        onMouseDown={e => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b flex items-start justify-between gap-4" style={{ borderColor: 'var(--border)' }}>
          <div className="min-w-0">
            <div className="text-sm" style={{ color: 'var(--foreground)' }}>{title}</div>
            {sub && <div className="mono text-[11px] mt-0.5" style={{ color: 'var(--muted-foreground)' }}>{sub}</div>}
          </div>
          <IconButton label="Close" onClick={onClose}><CloseIcon /></IconButton>
        </div>
        <div className="overflow-y-auto p-5 flex-1">{children}</div>
        {footer && <div className="px-5 py-3 border-t flex flex-wrap justify-end gap-2" style={{ borderColor: 'var(--border)' }}>{footer}</div>}
      </div>
    </div>
  )
}

export function Confirm({ open, onClose, onConfirm, title, body, confirmLabel, danger, typeToConfirm }: {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  body: ReactNode
  confirmLabel: string
  danger?: boolean
  typeToConfirm?: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <Modal open={open} onClose={onClose} title={title} width={440} footer={
      <>
        <Button kind="secondary" size="sm" onClick={onClose}>Cancel</Button>
        <Button
          kind={danger ? 'danger' : 'primary'}
          size="sm"
          onClick={() => {
            if (typeToConfirm && inputRef.current?.value.trim() !== typeToConfirm) { inputRef.current?.focus(); return }
            onConfirm()
            onClose()
          }}
        >
          {confirmLabel}
        </Button>
      </>
    }>
      <div className="text-sm leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{body}</div>
      {typeToConfirm && (
        <div className="mt-4">
          <label htmlFor="confirm-input" className="mono text-[10px] uppercase tracking-widest block mb-1" style={{ color: 'var(--muted-foreground)' }}>
            Type <span style={{ color: 'var(--foreground)' }}>{typeToConfirm}</span> to confirm
          </label>
          <input id="confirm-input" ref={inputRef} type="text" autoComplete="off" className="w-full px-3 py-2 text-sm rounded outline-none" style={{ background: 'var(--muted)', border: '1px solid var(--border)' }} />
        </div>
      )}
    </Modal>
  )
}

export function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="w-7 h-7 rounded flex items-center justify-center transition-colors hover:bg-[var(--secondary)] shrink-0"
      style={{ color: 'var(--muted-foreground)' }}
    >
      {children}
    </button>
  )
}

export function Toasts() {
  const { toasts } = useApp()
  return (
    <div className="fixed bottom-4 right-4 z-[70] flex flex-col gap-2 items-end pointer-events-none" aria-live="polite">
      {toasts.map(t => (
        <div
          key={t.id}
          className="toast rounded px-4 py-2.5 text-xs shadow-lg max-w-sm"
          style={{
            background: t.kind === 'error' ? '#fef2f2' : t.kind === 'warn' ? '#fffbeb' : 'var(--primary)',
            color: t.kind === 'error' ? '#b91c1c' : t.kind === 'warn' ? '#92400e' : '#fff',
            border: t.kind === 'ok' ? 'none' : '1px solid var(--border)',
          }}
        >
          {t.text}
        </div>
      ))}
    </div>
  )
}

export function Empty({ title, body, action, height = 220 }: { title: string; body?: ReactNode; action?: ReactNode; height?: number }) {
  return (
    <div className="flex flex-col items-center justify-center text-center px-6 gap-2" style={{ minHeight: height }}>
      <div className="text-sm" style={{ color: 'var(--foreground)' }}>{title}</div>
      {body && <div className="text-xs max-w-sm leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>{body}</div>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function Spinner({ light = false, size = 16 }: { light?: boolean; size?: number }) {
  return (
    <div
      className="border-2 rounded-full animate-spin shrink-0"
      style={{ width: size, height: size, borderColor: light ? '#fff' : 'var(--primary)', borderTopColor: 'transparent' }}
      aria-hidden
    />
  )
}

export function Checkbox({ id, checked, onChange, label, disabled }: { id: string; checked: boolean; onChange: (v: boolean) => void; label: ReactNode; disabled?: boolean }) {
  return (
    <label htmlFor={id} className="flex items-center gap-3 py-2 cursor-pointer" style={{ opacity: disabled ? 0.6 : 1 }}>
      <input id={id} type="checkbox" checked={checked} disabled={disabled} onChange={e => onChange(e.target.checked)} className="accent-[var(--primary)]" />
      <span className="text-xs" style={{ color: 'var(--foreground)' }}>{label}</span>
    </label>
  )
}

export function Bar({ value, color = 'var(--primary)', height = 4, track = 'var(--border)' }: { value: number; color?: string; height?: number; track?: string }) {
  return (
    <div className="rounded-full overflow-hidden w-full" style={{ height, background: track }}>
      <div className="h-full rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: color }} />
    </div>
  )
}

/* ---------- Icons (from the prototype) ---------- */

export const StarIcon = ({ color = 'white', size = 14 }: { color?: string; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
    <path d="M8 1L9.5 6.5H15L10.5 10L12 15.5L8 12L4 15.5L5.5 10L1 6.5H6.5L8 1Z" fill={color} />
  </svg>
)

export const CloseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
    <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
)

export const UploadIcon = ({ size = 36 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ opacity: 0.4 }} aria-hidden>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="var(--foreground)" strokeWidth="1.5" strokeLinecap="round" />
    <polyline points="17 8 12 3 7 8" stroke="var(--foreground)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    <line x1="12" y1="3" x2="12" y2="15" stroke="var(--foreground)" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
)

export const SendIconWhite = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
    <path d="M14 2L7 9" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M14 2L10 14L7 9L2 6L14 2Z" fill="rgba(255,255,255,0.3)" stroke="white" strokeWidth="1.2" strokeLinejoin="round" />
  </svg>
)
