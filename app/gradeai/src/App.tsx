import { useCallback, useEffect, useState } from 'react'
import Sidebar, { BellIcon, shortCourse } from './components/Sidebar'
import Dashboard from './components/Dashboard'
import GradingSession from './components/GradingSession'
import RubricManager from './components/RubricManager'
import Submissions from './components/Submissions'
import CrowdmarkExport from './components/CrowdmarkExport'
import Settings from './components/Settings'
import ActivityPanel from './components/ActivityPanel'
import { Notice, Spinner, Toasts } from './components/ui'
import { useApp } from './context'
import { AcceptInvite, FirstRun, SignIn } from './components/Auth'
import type { View } from './lib/types'

/* Hash names for each view (claude.ai reserves #settings, so Settings is #course-settings). */
const HASH: Record<View, string> = {
  dashboard: 'dashboard', grade: 'grade-batch', rubrics: 'rubrics', submissions: 'submissions', crowdmark: 'crowdmark', settings: 'course-settings',
}
function viewFromHash(): View {
  const h = (typeof location !== 'undefined' ? location.hash : '').replace('#', '')
  return (Object.entries(HASH).find(([, v]) => v === h)?.[0] as View) ?? 'dashboard'
}

export default function App() {
  const { auth, ready, offline, activity, lastSeenActivity, markActivitySeen, settings, me } = useApp()
  const [activeView, setView] = useState<View>(viewFromHash)
  const [notifOpen, setNotifOpen] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const [focusSubmission, setFocusSubmission] = useState<string | null>(null)

  useEffect(() => {
    const on = () => { if (!/^#invite=/.test(location.hash)) setView(viewFromHash()) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  const setActiveView = useCallback((v: View) => {
    setView(v)
    try { if (location.hash.replace('#', '') !== HASH[v]) history.replaceState(null, '', '#' + HASH[v]) } catch { /* sandboxed */ }
    document.getElementById('main')?.scrollTo({ top: 0 })
  }, [])

  const openSubmission = useCallback((id: string) => {
    setFocusSubmission(id)
    setActiveView('submissions')
  }, [setActiveView])

  const unreadCount = activity.filter(a => a.at > lastSeenActivity && a.by !== me.id).length

  function openNotifs() {
    setNotifOpen(true)
    markActivitySeen()
  }

  if (auth === 'loading') {
    return <div className="h-full flex items-center justify-center gap-3" style={{ color: 'var(--muted-foreground)' }}><Spinner /> <span className="text-sm">Loading…</span></div>
  }
  if (auth === 'invite') return <AcceptInvite />
  if (auth === 'setup') return <FirstRun />
  if (auth === 'signedOut') return <SignIn />

  return (
    <div className="flex h-full overflow-hidden" style={{ background: 'var(--background)' }}>
      <Sidebar
        activeView={activeView}
        setActiveView={setActiveView}
        onBellClick={openNotifs}
        unreadCount={unreadCount}
        open={navOpen}
        onClose={() => setNavOpen(false)}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Phone top bar */}
        <div className="md:hidden flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)', background: 'var(--card)' }}>
          <button type="button" onClick={() => setNavOpen(true)} aria-label="Open menu" className="w-8 h-8 flex items-center justify-center rounded hover:bg-[var(--secondary)]">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden><path d="M2 4h14M2 9h14M2 14h14" stroke="var(--foreground)" strokeWidth="1.5" strokeLinecap="round" /></svg>
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold" style={{ background: 'var(--primary)', color: '#fff' }}>AI</div>
            <span className="text-sm">GradeAI</span>
            <span className="mono text-[10px]" style={{ color: 'var(--muted-foreground)' }}>{shortCourse(settings.code)}</span>
          </div>
          <button type="button" onClick={openNotifs} aria-label="Activity" className="relative w-8 h-8 flex items-center justify-center rounded hover:bg-[var(--secondary)]" style={{ color: 'var(--muted-foreground)' }}>
            <BellIcon />
            {unreadCount > 0 && <span className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full" style={{ background: 'var(--primary)' }} />}
          </button>
        </div>

        <main id="main" className="flex-1 overflow-y-auto relative">
          {offline && (
            <div className="px-4 md:px-8 pt-4 max-w-screen-xl mx-auto">
              <Notice kind="warn">Lost connection to the GradeAI server. What you see may be out of date; it will update when the connection returns.</Notice>
            </div>
          )}
          {!ready ? (
            <div className="h-full flex items-center justify-center gap-3" style={{ color: 'var(--muted-foreground)' }}>
              <Spinner /> <span className="text-sm">Loading course…</span>
            </div>
          ) : (
            <>
              {activeView === 'dashboard' && <Dashboard setActiveView={setActiveView} openSubmission={openSubmission} />}
              {/* Grade Batch stays mounted so a running batch keeps going while you look at other pages */}
              <div hidden={activeView !== 'grade'}><GradingSession setActiveView={setActiveView} /></div>
              {activeView === 'rubrics' && <RubricManager />}
              {activeView === 'submissions' && <Submissions focusId={focusSubmission} clearFocus={() => setFocusSubmission(null)} />}
              {activeView === 'crowdmark' && <CrowdmarkExport />}
              {activeView === 'settings' && <Settings />}
            </>
          )}
        </main>
      </div>

      <ActivityPanel open={notifOpen} onClose={() => setNotifOpen(false)} />
      <Toasts />
    </div>
  )
}
