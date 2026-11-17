/* Same-origin JSON API client. Every mutating request carries X-GradeAI (the server's CSRF guard). */

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message) }
}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const method = opts.method ?? (opts.body !== undefined || opts.form ? 'POST' : 'GET')
  const headers: Record<string, string> = { 'X-GradeAI': '1' }
  let body: BodyInit | undefined
  if (opts.form) body = opts.form
  else if (opts.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(opts.body) }
  let res: Response
  try {
    res = await fetch(`/api${path}`, { method, headers, body, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'offline', 'Can’t reach the GradeAI server. Check your connection.')
  }
  const text = await res.text()
  let data: Record<string, unknown> = {}
  try { data = text ? JSON.parse(text) : {} } catch { /* non-JSON */ }
  if (!res.ok) {
    const code = String(data.error ?? res.status)
    const fallback = res.status === 401 ? 'Your session ended. Sign in again.' : res.status === 403 ? 'Your role can’t do this.' : 'Something went wrong on the server.'
    throw new ApiError(res.status, code, String(data.message ?? fallback))
  }
  return data as T
}

/** Save a generated file to the user's computer. */
export function downloadFile(filename: string, data: string | Blob, type = 'text/csv;charset=utf-8') {
  const blob = typeof data === 'string' ? new Blob([data], { type }) : data
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
