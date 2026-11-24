import { useMemo } from 'react'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { tokenizeLatex } from '../lib/latex'

function renderKatex(tex: string, displayMode: boolean): string {
  return katex.renderToString(tex, {
    displayMode,
    throwOnError: false,
    strict: 'ignore',
    trust: false,
    errorColor: '#dc2626',
  })
}

export default function LatexExtract({
  content,
  className = '',
}: {
  content: string
  className?: string
}) {
  const tokens = useMemo(() => tokenizeLatex(content), [content])

  return (
    <div
      className={`rounded p-4 text-[13px] leading-relaxed overflow-auto ${className}`}
      style={{ background: 'var(--secondary)', color: 'var(--foreground)', border: '1px solid var(--border)' }}
    >
      <div className="whitespace-pre-wrap break-words">
        {tokens.map((tok, i) => {
          if (tok.type === 'text') {
            return <span key={i}>{tok.value}</span>
          }
          if (tok.type === 'page-break') {
            return (
              <span key={i} className="flex items-center gap-2 my-3 select-none">
                <span className="flex-1 h-px" style={{ background: 'var(--border)' }} />
                <span
                  className="mono text-[10px] uppercase tracking-widest px-2 py-0.5 rounded"
                  style={{ background: 'var(--background)', color: 'var(--muted-foreground)', border: '1px solid var(--border)' }}
                >
                  {tok.value}
                </span>
                <span className="flex-1 h-px" style={{ background: 'var(--border)' }} />
              </span>
            )
          }
          if (tok.type === 'illegible') {
            return (
              <span
                key={i}
                className="mono text-[11px] px-1.5 py-0.5 rounded mx-0.5"
                style={{ background: 'rgba(245,158,11,0.12)', color: '#b45309' }}
              >
                {tok.value}
              </span>
            )
          }
          if (tok.type === 'display-math') {
            return (
              <span
                key={i}
                className="block my-2.5 overflow-x-auto py-1"
                dangerouslySetInnerHTML={{ __html: renderKatex(tok.value, true) }}
              />
            )
          }
          return (
            <span
              key={i}
              className="inline-block align-baseline mx-0.5"
              dangerouslySetInnerHTML={{ __html: renderKatex(tok.value, false) }}
            />
          )
        })}
      </div>
    </div>
  )
}
