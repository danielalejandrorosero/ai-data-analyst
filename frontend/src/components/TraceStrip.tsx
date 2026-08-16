import type { ReactNode } from 'react'

interface TraceStripProps {
  segments: string[]
  right?: ReactNode
}

export function TraceStrip({ segments, right }: TraceStripProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-ink-700 bg-ink-900 px-4 py-2 font-mono text-xs text-paper-400">
      <span>
        <span className="text-signal-500">$</span>{' '}
        {segments.map((segment, i) => (
          <span key={segment}>
            {i > 0 && <span className="text-ink-400"> · </span>}
            {segment}
          </span>
        ))}
      </span>
      {right}
    </div>
  )
}
