import { personName, useApp, usePeople } from '../context'
import { relTime } from '../lib/format'
import type { ActivityType } from '../lib/types'
import { CloseIcon, IconButton } from './ui'

export default function ActivityPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { activity, lastSeenActivity, me } = useApp()
  const people = usePeople(activity.map(a => a.by))
  const shown = activity.slice(0, 40)

  return (
    <>
      {open && <div className="fixed inset-0 z-40" onClick={onClose} style={{ background: 'rgba(0,0,0,0.15)' }} />}
      <aside
        className="fixed top-0 right-0 h-full z-50 flex flex-col w-full sm:w-[360px]"
        aria-hidden={!open}
        style={{
          background: 'var(--background)',
          borderLeft: '1px solid var(--border)',
          transform: open ? 'translateX(0)' : 'translateX(100%)',
          visibility: open ? 'visible' : 'hidden',
          transition: 'transform 0.25s cubic-bezier(0.4,0,0.2,1), visibility 0.25s',
          boxShadow: open ? '-8px 0 32px rgba(30,55,101,0.08)' : 'none',
        }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <div className="text-sm" style={{ color: 'var(--foreground)' }}>Activity</div>
            <div className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
              {activity.length === 0 ? 'Nothing yet' : `${shown.length} recent ${shown.length === 1 ? 'event' : 'events'}`}
            </div>
          </div>
          <IconButton label="Close activity" onClick={onClose}><CloseIcon /></IconButton>
        </div>
        <div className="flex-1 overflow-y-auto">
          {shown.length === 0 && (
            <div className="px-5 py-10 text-xs text-center leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
              Grading batches, rubric changes, flagged submissions and exports will show up here for the whole course team.
            </div>
          )}
          {shown.map((n, i) => {
            const unread = n.at > lastSeenActivity && n.by !== me.id
            return (
              <div
                key={n.id}
                className="px-5 py-4 flex gap-3"
                style={{ borderBottom: i < shown.length - 1 ? '1px solid var(--border)' : 'none', background: unread ? 'var(--muted)' : 'transparent' }}
              >
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-0.5" style={{ background: iconBg(n.type), color: iconColor(n.type) }}>
                  <NotifIcon type={n.type} />
                </div>
                <div className="min-w-0">
                  <div className="text-xs mb-0.5" style={{ color: 'var(--foreground)' }}>{n.title}</div>
                  <div className="text-xs leading-relaxed break-words" style={{ color: 'var(--muted-foreground)' }}>{n.body}</div>
                  <div className="text-[10px] mt-1.5" style={{ color: 'var(--muted-foreground)', opacity: 0.8 }}>
                    {relTime(n.at)} · {n.by === me.id ? 'You' : personName(people, n.by)}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </aside>
    </>
  )
}

function iconBg(type: ActivityType) {
  if (type === 'grade') return '#edf0f7'
  if (type === 'rubric') return '#e8f0fe'
  if (type === 'export') return '#e6f4ea'
  if (type === 'flag') return '#fef3e2'
  return '#fef9e7'
}
function iconColor(type: ActivityType) {
  if (type === 'export') return '#1a7340'
  if (type === 'flag' || type === 'system') return '#b45309'
  return '#1e3765'
}

function NotifIcon({ type }: { type: ActivityType }) {
  if (type === 'grade') return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M8 1L9.5 6.5H15L10.5 10L12 15.5L8 12L4 15.5L5.5 10L1 6.5H6.5L8 1Z" fill="currentColor" opacity="0.8" />
    </svg>
  )
  if (type === 'rubric') return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <rect x="2" y="1" width="9" height="14" rx="1" stroke="currentColor" strokeWidth="1.3" opacity="0.7" />
      <line x1="5" y1="5" x2="9" y2="5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5" y1="8" x2="9" y2="8" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  )
  if (type === 'export') return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path d="M14 2L7 9M14 2L10 14L7 9L2 6L14 2Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  )
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" />
      <line x1="8" y1="6" x2="8" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="8" cy="11" r="0.7" fill="currentColor" />
    </svg>
  )
}
