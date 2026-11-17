import type { Role, View } from '../lib/types'
import { ROLE_COLORS, ROLE_LABELS, useApp } from '../context'
import { Avatar } from './ui'
import ModelBadge from './ModelBadge'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: GridIcon },
  { id: 'grade', label: 'Grade Batch', icon: SparkIcon },
  { id: 'rubrics', label: 'Rubrics', icon: DocIcon },
  { id: 'submissions', label: 'Submissions', icon: StackIcon },
  { id: 'crowdmark', label: 'Crowdmark', icon: SendIcon },
] as const

export function shortCourse(code: string) {
  return code.match(/^[A-Za-z]{3}\d{3}/)?.[0]?.toUpperCase() ?? code.split(' ')[0]
}

interface Props {
  activeView: View
  setActiveView: (v: View) => void
  onBellClick: () => void
  unreadCount: number
  open: boolean
  onClose: () => void
}

export default function Sidebar({ activeView, setActiveView, onBellClick, unreadCount, open, onClose }: Props) {
  const { settings, me, role, actualRole, isAdmin, setPreviewRole, previewRole, submissions, signOut } = useApp()
  const reviewCount = submissions.filter(s => s.status === 'review' && s.assignment === settings.currentAssignment).length
  const showSwitcher = isAdmin

  const go = (v: View) => { setActiveView(v); onClose() }

  return (
    <>
      {open && <div className="fixed inset-0 z-30 md:hidden" style={{ background: 'rgba(0,0,0,0.2)' }} onClick={onClose} />}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-40 flex flex-col w-60 shrink-0 border-r transition-transform duration-200 md:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}
        style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="px-5 pt-6 pb-5 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold shrink-0" style={{ background: 'var(--primary)', color: '#fff' }}>
                AI
              </div>
              <div className="min-w-0">
                <div className="text-sm tracking-tight" style={{ color: 'var(--foreground)' }}>GradeAI</div>
                <div className="mono text-[10px] truncate" style={{ color: 'var(--muted-foreground)' }}>{shortCourse(settings.code)} · {settings.term}</div>
              </div>
            </div>
            <button
              type="button"
              onClick={onBellClick}
              className="relative w-7 h-7 rounded flex items-center justify-center transition-colors hover:bg-[var(--secondary)]"
              style={{ color: 'var(--muted-foreground)' }}
              title="Activity"
              aria-label={`Activity${unreadCount ? `, ${unreadCount} unread` : ''}`}
            >
              <BellIcon />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-0.5 rounded-full text-[9px] font-bold flex items-center justify-center" style={{ background: 'var(--primary)', color: '#fff' }}>
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 flex flex-col gap-0.5 overflow-y-auto">
          {NAV.map(({ id, label, icon: Icon }) => (
            <NavButton key={id} active={activeView === id} onClick={() => go(id)} label={label} icon={Icon}
              badge={id === 'submissions' && reviewCount > 0 ? reviewCount : undefined} />
          ))}
          <div className="my-3 border-t" style={{ borderColor: 'var(--border)' }} />
          <NavButton active={activeView === 'settings'} onClick={() => go('settings')} label="Settings" icon={GearIcon} />
          <div className="mt-auto pt-4 px-3"><ModelBadge compact /></div>
        </nav>

        {/* Role switcher + current user */}
        <div className="px-3 pb-4 border-t pt-4" style={{ borderColor: 'var(--border)' }}>
          {showSwitcher && (
            <>
              <div className="mono text-[10px] uppercase tracking-widest mb-2 px-1" style={{ color: 'var(--muted-foreground)' }}>
                Preview as
              </div>
              <div className="flex flex-col gap-1" role="radiogroup" aria-label="Role">
                {(['professor', 'ta', 'admin'] as Role[]).map(r => {
                  const selected = role === r
                  const tag = r === actualRole ? ' (you)' : ''
                  return (
                    <button
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      key={r}
                      onClick={() => setPreviewRole(r)}
                      className="flex items-center gap-2 px-2 py-1.5 rounded text-xs transition-all duration-150 text-left"
                      style={{ background: selected ? 'var(--secondary)' : 'transparent', color: selected ? 'var(--foreground)' : 'var(--muted-foreground)' }}
                    >
                      <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold" style={{ background: ROLE_COLORS[r], color: '#fff' }}>
                        {r === 'ta' ? 'TA' : r[0].toUpperCase()}
                      </div>
                      <span>{ROLE_LABELS[r]}{tag}</span>
                    </button>
                  )
                })}
              </div>
              {previewRole && (
                <button type="button" onClick={() => setPreviewRole(null)} className="mono text-[10px] mt-1 px-2 hover:opacity-70" style={{ color: 'var(--primary)' }}>
                  Stop previewing
                </button>
              )}
            </>
          )}

          <div className={`${showSwitcher ? 'mt-3' : ''} rounded p-3 flex items-center gap-3`} style={{ background: 'var(--secondary)' }}>
            <Avatar name={me.name} color={ROLE_COLORS[actualRole]} />
            <div className="min-w-0 flex-1">
              <div className="text-xs truncate" style={{ color: 'var(--foreground)' }}>{me.name}</div>
              <div className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{ROLE_LABELS[actualRole]}</div>
            </div>
            <button type="button" onClick={signOut} title="Sign out" aria-label="Sign out" className="w-7 h-7 rounded flex items-center justify-center hover:bg-[var(--card)] shrink-0" style={{ color: 'var(--muted-foreground)' }}>
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden><path d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3M10.5 11.5 14 8l-3.5-3.5M14 8H6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}

function NavButton({ active, onClick, label, icon: Icon, badge }: { active: boolean; onClick: () => void; label: string; icon: (p: { size: number; active: boolean }) => React.ReactElement; badge?: number }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      className="flex items-center gap-3 px-3 py-2 rounded text-sm w-full text-left transition-all duration-150"
      style={{
        background: active ? 'var(--secondary)' : 'transparent',
        color: active ? 'var(--foreground)' : 'var(--muted-foreground)',
        borderLeft: active ? '2px solid var(--primary)' : '2px solid transparent',
      }}
    >
      <Icon size={15} active={active} />
      <span className="flex-1">{label}</span>
      {badge !== undefined && (
        <span className="mono text-[10px] px-1.5 rounded" style={{ background: 'rgba(245,158,11,0.18)', color: '#b45309' }}>{badge}</span>
      )}
    </button>
  )
}

export function BellIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M8 1a5 5 0 0 1 5 5v3l1.5 2H1.5L3 9V6a5 5 0 0 1 5-5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M6.5 13.5a1.5 1.5 0 0 0 3 0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function GridIcon({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="1" y="1" width="6" height="6" rx="1" fill={active ? 'var(--primary)' : 'currentColor'} opacity={active ? 1 : 0.6} />
      <rect x="9" y="1" width="6" height="6" rx="1" fill={active ? 'var(--primary)' : 'currentColor'} opacity={active ? 0.6 : 0.4} />
      <rect x="1" y="9" width="6" height="6" rx="1" fill={active ? 'var(--primary)' : 'currentColor'} opacity={active ? 0.6 : 0.4} />
      <rect x="9" y="9" width="6" height="6" rx="1" fill={active ? 'var(--primary)' : 'currentColor'} opacity={active ? 0.4 : 0.25} />
    </svg>
  )
}

function SparkIcon({ size, active }: { size: number; active: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M8 1L9.5 6.5H15L10.5 10L12 15.5L8 12L4 15.5L5.5 10L1 6.5H6.5L8 1Z" fill={active ? 'var(--primary)' : 'currentColor'} opacity={active ? 1 : 0.6} />
    </svg>
  )
}

function DocIcon({ size, active }: { size: number; active: boolean }) {
  const c = active ? 'var(--primary)' : 'currentColor'
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="2" y="1" width="9" height="14" rx="1" fill={c} opacity={active ? 0.3 : 0.2} />
      <rect x="2" y="1" width="9" height="14" rx="1" stroke={c} strokeWidth="1.2" opacity={active ? 1 : 0.6} />
      <line x1="5" y1="5" x2="9" y2="5" stroke={c} strokeWidth="1.2" opacity={active ? 1 : 0.6} />
      <line x1="5" y1="8" x2="9" y2="8" stroke={c} strokeWidth="1.2" opacity={active ? 1 : 0.6} />
      <line x1="5" y1="11" x2="8" y2="11" stroke={c} strokeWidth="1.2" opacity={active ? 1 : 0.6} />
      <path d="M10 1L14 5H10V1Z" fill={c} opacity={active ? 0.6 : 0.4} />
    </svg>
  )
}

function StackIcon({ size, active }: { size: number; active: boolean }) {
  const c = active ? 'var(--primary)' : 'currentColor'
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="1" y="3" width="14" height="3" rx="1" fill={c} opacity={active ? 1 : 0.6} />
      <rect x="1" y="7" width="14" height="3" rx="1" fill={c} opacity={active ? 0.6 : 0.4} />
      <rect x="1" y="11" width="14" height="3" rx="1" fill={c} opacity={active ? 0.3 : 0.2} />
    </svg>
  )
}

function SendIcon({ size, active }: { size: number; active: boolean }) {
  const c = active ? 'var(--primary)' : 'currentColor'
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M14 2L7 9" stroke={c} strokeWidth="1.5" strokeLinecap="round" opacity={active ? 1 : 0.6} />
      <path d="M14 2L10 14L7 9L2 6L14 2Z" fill={c} opacity={active ? 0.3 : 0.15} stroke={c} strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

function GearIcon({ size, active }: { size: number; active: boolean }) {
  const c = active ? 'var(--primary)' : 'currentColor'
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="2.5" stroke={c} strokeWidth="1.3" opacity={active ? 1 : 0.6} />
      <path d="M8 1v2M8 13v2M1 8h2M13 8h2M2.93 2.93l1.41 1.41M11.66 11.66l1.41 1.41M2.93 13.07l1.41-1.41M11.66 4.34l1.41-1.41" stroke={c} strokeWidth="1.3" strokeLinecap="round" opacity={active ? 0.7 : 0.4} />
    </svg>
  )
}
