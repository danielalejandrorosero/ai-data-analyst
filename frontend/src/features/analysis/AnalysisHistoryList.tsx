import { History } from 'lucide-react'
import type { AnalysisListItem, AnalysisStatus } from '../../api/analyses'
import { isTerminalStatus } from '../../api/analyses'

function statusDotClass(status: AnalysisStatus): string {
  if (status === 'COMPLETED') return 'bg-success-500'
  if (status === 'FAILED' || status === 'TIMED_OUT') return 'bg-danger-500'
  if (status === 'CANCELLED') return 'bg-ink-400'
  return 'bg-signal-500 animate-pulse'
}

function formatRelative(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

interface AnalysisHistoryListProps {
  analyses: AnalysisListItem[]
  activeId: string | null
  onSelect: (analysisId: string) => void
}

export function AnalysisHistoryList({ analyses, activeId, onSelect }: AnalysisHistoryListProps) {
  return (
    <aside className="flex w-72 shrink-0 flex-col gap-3 rounded-xl border border-ink-700 bg-ink-900/40 p-4">
      <p className="flex items-center gap-2 font-mono text-xs text-paper-400">
        <History className="h-3.5 w-3.5" aria-hidden="true" />
        Historial
      </p>

      {analyses.length === 0 && (
        <p className="font-body text-xs text-paper-400">Todavía no hiciste ninguna pregunta.</p>
      )}

      <ul className="flex flex-col divide-y divide-ink-800 overflow-y-auto">
        {analyses.map((analysis) => (
          <li key={analysis.id}>
            <button
              type="button"
              onClick={() => onSelect(analysis.id)}
              className={`flex w-full flex-col gap-1 rounded-md px-3 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 ${
                analysis.id === activeId ? 'bg-signal-500/10' : 'hover:bg-ink-800'
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusDotClass(analysis.status)}`}
                  aria-hidden="true"
                />
                <span className="line-clamp-2 font-body text-xs text-paper-100">{analysis.question}</span>
              </div>
              <span className="font-mono text-[10px] text-paper-400">
                {formatRelative(analysis.created_at)}
                {!isTerminalStatus(analysis.status) && ' · en curso'}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
