import { MessagesSquare } from 'lucide-react'
import type { Dataset } from '../../api/datasets'
import type { AnalysisListItem } from '../../api/analyses'
import { isTerminalStatus } from '../../api/analyses'

function formatRelative(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface ChatEntry {
  dataset: Dataset
  count: number
  lastQuestion: string | null
  lastAt: string | null
  running: boolean
}

function buildEntries(datasets: Dataset[], analyses: AnalysisListItem[]): ChatEntry[] {
  const entries = datasets.map((dataset) => {
    const own = analyses.filter((a) => a.dataset_id === dataset.id)
    // El backend lista mas recientes primero (GET /analyses).
    const last = own[0] ?? null
    return {
      dataset,
      count: own.length,
      lastQuestion: last?.question ?? null,
      lastAt: last?.created_at ?? null,
      running: own.some((a) => !isTerminalStatus(a.status)),
    }
  })
  // Chats con actividad reciente arriba; datasets sin chat al final.
  return entries.sort((a, b) => {
    if (a.lastAt && b.lastAt) return b.lastAt.localeCompare(a.lastAt)
    if (a.lastAt) return -1
    if (b.lastAt) return 1
    return a.dataset.name.localeCompare(b.dataset.name)
  })
}

interface DatasetChatListProps {
  datasets: Dataset[]
  analyses: AnalysisListItem[]
  activeDatasetId: string | null
  onSelect: (datasetId: string) => void
}

// Un chat por dataset: toda la conversacion sobre un dataset vive en un
// mismo hilo (pedido explicito del usuario) - el sidebar lista los hilos,
// no preguntas sueltas.
export function DatasetChatList({ datasets, analyses, activeDatasetId, onSelect }: DatasetChatListProps) {
  const entries = buildEntries(datasets, analyses)

  return (
    <aside className="flex w-72 shrink-0 flex-col gap-3 rounded-xl border border-ink-700 bg-ink-900/40 p-4">
      <p className="flex shrink-0 items-center gap-2 font-mono text-xs text-paper-400">
        <MessagesSquare className="h-3.5 w-3.5" aria-hidden="true" />
        Chats por dataset
      </p>

      <ul className="flex min-h-0 flex-1 flex-col divide-y divide-ink-800 overflow-y-auto">
        {entries.map((entry) => (
          <li key={entry.dataset.id}>
            <button
              type="button"
              onClick={() => onSelect(entry.dataset.id)}
              className={`flex w-full flex-col gap-1 rounded-md px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 ${
                entry.dataset.id === activeDatasetId ? 'bg-signal-500/10' : 'hover:bg-ink-800'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-body text-xs font-semibold text-paper-100">
                  {entry.dataset.name}
                </span>
                <span
                  className={`shrink-0 rounded-full px-1.5 font-mono text-[10px] leading-4 ${
                    entry.running
                      ? 'animate-pulse bg-signal-500/15 text-signal-500'
                      : 'bg-ink-800 text-paper-400'
                  }`}
                >
                  {entry.count}
                </span>
              </div>
              {entry.lastQuestion ? (
                <>
                  <span className="line-clamp-1 font-body text-xs text-paper-400">{entry.lastQuestion}</span>
                  <span className="font-mono text-[10px] text-ink-400">
                    {entry.lastAt && formatRelative(entry.lastAt)}
                    {entry.running && ' · en curso'}
                  </span>
                </>
              ) : (
                <span className="font-body text-xs text-ink-400">Sin preguntas todavía</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
