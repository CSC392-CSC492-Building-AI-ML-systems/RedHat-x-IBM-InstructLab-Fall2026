import { useEffect, useState } from 'react'
import { useApp } from '../context'

function until(ts: number) {
  const d = new Date(ts)
  const sameDay = d.toDateString() === new Date().toDateString()
  return sameDay
    ? d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    : d.toLocaleString([], { weekday: 'short', hour: 'numeric', minute: '2-digit' })
}

/** Online/offline state of the fine-tuned model running on Fir, as reported by its worker. */
export default function ModelBadge({ detailed = false, compact = false }: { detailed?: boolean; compact?: boolean }) {
  const { model } = useApp()
  const [, tick] = useState(0)
  useEffect(() => { const t = setInterval(() => tick(x => x + 1), 30000); return () => clearInterval(t) }, [])
  const color = model.online ? '#22c55e' : '#f59e0b'
  const queue = model.waiting + model.grading

  if (compact) {
    return (
      <div className="flex items-center gap-2 mono text-[10px]" style={{ color: 'var(--muted-foreground)' }} title={model.online ? `Model online${model.slurmJobId ? ` · Fir job ${model.slurmJobId}` : ''}` : 'Model offline'}>
        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
        <span className="truncate">{model.online ? 'Model online' : 'Model offline'}{queue ? ` · ${queue} in queue` : ''}</span>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-start gap-3">
        <span className="w-2.5 h-2.5 rounded-full shrink-0 mt-1" style={{ background: color }} />
        <div className="min-w-0">
          <div className="text-sm" style={{ color: 'var(--foreground)' }}>{model.model ?? 'Fine-tuned model'}</div>
          <div className="mono text-[10px] leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
            {model.online
              ? <>Online on Fir{model.slurmJobId ? ` · job ${model.slurmJobId}` : ''}{model.endsAt ? ` · until ${until(model.endsAt)}` : ''}</>
              : <>Offline{model.lastSeen ? ` · last seen ${new Date(model.lastSeen).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}` : ' · no Fir job has connected yet'}</>}
          </div>
        </div>
      </div>
      {detailed && (
        <div className="mt-3 mono text-[10px] px-2 py-1.5 rounded leading-relaxed" style={{ background: 'var(--secondary)', color: 'var(--muted-foreground)' }}>
          {queue
            ? `${model.grading} grading · ${model.waiting} waiting`
            : 'Queue empty'}
          {!model.online && <><br />Files wait here and grade automatically when the Fir model connects (npm run model:connect).</>}
        </div>
      )}
    </div>
  )
}
