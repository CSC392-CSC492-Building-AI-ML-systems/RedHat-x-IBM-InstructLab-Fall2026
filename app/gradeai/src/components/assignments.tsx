import { useMemo } from 'react'
import { useApp } from '../context'

/** Every assignment the course knows about: the current one, those with rubrics, and those with submissions. */
export function useAssignments() {
  const { settings, rubrics, submissions } = useApp()
  return useMemo(() => {
    const latest = new Map<string, number>()
    const bump = (a: string, t: number) => { if (a) latest.set(a, Math.max(latest.get(a) ?? 0, t)) }
    bump(settings.currentAssignment, Number.MAX_SAFE_INTEGER)
    for (const r of rubrics) bump(r.assignment, r.updatedAt ?? 0)
    for (const s of submissions) bump(s.assignment, s.updatedAt ?? 0)
    return [...latest.entries()].sort((a, b) => b[1] - a[1]).map(([a]) => a)
  }, [settings.currentAssignment, rubrics, submissions])
}

export function AssignmentPicker({ value, onChange, id }: { value: string; onChange: (v: string) => void; id: string }) {
  const list = useAssignments()
  const options = list.includes(value) ? list : [value, ...list]
  return (
    <div className="relative">
      <label htmlFor={id} className="sr-only">Assignment</label>
      <select
        id={id}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="mono text-xs rounded pl-3 pr-8 py-2 outline-none appearance-none cursor-pointer"
        style={{ background: 'var(--card)', color: 'var(--foreground)', border: '1px solid var(--border)' }}
      >
        {options.map(a => <option key={a} value={a}>{a}</option>)}
      </select>
      <svg className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" width="10" height="10" viewBox="0 0 16 16" fill="none" aria-hidden>
        <path d="M4 6l4 4 4-4" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  )
}
