import type { Response } from 'express'

/** Server-Sent Events: pushes document changes and model status to open browsers. */
interface Client { res: Response; userId: string }
const clients = new Set<Client>()

export function addClient(res: Response, userId: string) {
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  })
  res.write('retry: 3000\n\n')
  const c: Client = { res, userId }
  clients.add(c)
  const ping = setInterval(() => res.write(': ping\n\n'), 25000)
  res.on('close', () => { clearInterval(ping); clients.delete(c) })
}

function send(c: Client, event: string, data: unknown) {
  try { c.res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`) } catch { clients.delete(c) }
}

/** A document changed. Private per-user docs only reach their owner; large content docs go out without data. */
export function broadcastDoc(path: string, op: 'set' | 'delete', data?: unknown) {
  const priv = path.match(/^data\/users\/([^/]+)\//)
  const withData = op === 'set' && !path.startsWith('submissionContent/')
  for (const c of clients) {
    if (priv && priv[1] !== c.userId) continue
    send(c, 'doc', { path, op, data: withData ? data : undefined })
  }
}

export function broadcast(event: string, data: unknown) {
  for (const c of clients) send(c, event, data)
}

export function disconnectUser(userId: string) {
  for (const c of clients) if (c.userId === userId) { try { c.res.end() } catch { /* closed */ } clients.delete(c) }
}
