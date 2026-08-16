import { Clock, Columns3, Database, Rows3 } from 'lucide-react'
import type { Dataset } from '../../api/datasets'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function SourceBadge({ dataset }: { dataset: Dataset }) {
  if (dataset.source_type === 'postgres') {
    return (
      <span className="flex h-9 w-9 items-center justify-center rounded-md bg-code-500/10 text-code-500">
        <Database className="h-4.5 w-4.5" aria-hidden="true" />
      </span>
    )
  }

  // "upload" - csv y xlsx comparten badge de archivo, distinguidos por la
  // extension real guardada al importar (backend/app/db/models/dataset.py).
  const label = dataset.source_extension === 'xlsx' ? 'X' : 'CSV'
  return (
    <span
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-success-500/10 font-mono text-[11px] font-bold text-success-500"
      title={dataset.source_extension === 'xlsx' ? 'Excel' : 'CSV'}
    >
      {label}
    </span>
  )
}

interface DatasetCardProps {
  dataset: Dataset
  onViewSchema: (dataset: Dataset) => void
}

export function DatasetCard({ dataset, onViewSchema }: DatasetCardProps) {
  return (
    <button
      type="button"
      onClick={() => onViewSchema(dataset)}
      className="flex flex-col gap-3 rounded-xl border border-ink-700 bg-ink-900/60 p-4 text-left transition-colors hover:border-ink-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <SourceBadge dataset={dataset} />
          <span className="font-body text-sm font-semibold text-paper-100">{dataset.name}</span>
        </div>
        <span className="flex items-center gap-1.5 rounded-full border border-success-500/30 bg-success-500/10 px-2 py-0.5 font-mono text-[11px] text-success-500">
          <span className="h-1.5 w-1.5 rounded-full bg-success-500" aria-hidden="true" />
          Listo
        </span>
      </div>

      <div className="border-t border-ink-800" />

      <div className="flex flex-col gap-2 font-mono text-xs text-paper-400">
        <span className="flex items-center gap-2">
          <Rows3 className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
          {dataset.row_count.toLocaleString('es-AR')} filas
        </span>
        <span className="flex items-center gap-2">
          <Columns3 className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
          {dataset.column_count} columnas
        </span>
        <span className="flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
          Actualizado: {formatDate(dataset.created_at)}
        </span>
      </div>
    </button>
  )
}
