export const GREEN = '#22c55e'
export const AMBER = '#f59e0b'
export const RED = '#ef4444'

export function scoreColor(score: number, total: number) {
  const p = total > 0 ? score / total : 0
  if (p >= 0.8) return GREEN
  if (p >= 0.6) return AMBER
  return RED
}

export function confColor(c: number | null) {
  if (c === null) return 'var(--muted-foreground)'
  if (c >= 90) return GREEN
  if (c >= 70) return AMBER
  return RED
}

export function relTime(ts: number | null | undefined, now = Date.now()) {
  if (!ts) return '—'
  const s = Math.max(0, Math.round((now - ts) / 1000))
  if (s < 45) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.round(h / 24)
  if (d === 1) return 'Yesterday'
  if (d < 7) return `${d}d ago`
  return shortDate(ts)
}

export function shortDate(ts: number) {
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function longDate(ts: number) {
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function fmtScore(n: number | null) {
  if (n === null) return '—'
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

export function greeting(d = new Date()) {
  const h = d.getHours()
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export function initials(name: string) {
  const parts = name.replace(/^(prof\.?|dr\.?)\s+/i, '').split(/\s+/).filter(Boolean)
  return (parts.slice(0, 2).map(p => p[0]).join('') || '?').toUpperCase()
}

/* ---------- CSV ---------- */

export function toCSV(rows: (string | number | null | undefined)[][]) {
  return rows
    .map(r => r.map(v => {
      const s = v === null || v === undefined ? '' : String(v)
      return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
    }).join(','))
    .join('\r\n')
}

export function parseCSV(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cur = ''
  let q = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cur += '"'; i++ }
      else if (c === '"') q = false
      else cur += c
    } else if (c === '"') q = true
    else if (c === ',') { row.push(cur); cur = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      row.push(cur); cur = ''
      if (row.some(x => x.trim())) rows.push(row)
      row = []
    } else cur += c
  }
  row.push(cur)
  if (row.some(x => x.trim())) rows.push(row)
  return rows
}

export function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}
