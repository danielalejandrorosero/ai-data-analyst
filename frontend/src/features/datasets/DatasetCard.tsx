import { Clock, Columns3, Database, FileSpreadsheet, FileText, Rows3 } from 'lucide-react'
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

// Un color + icono + etiqueta visible por formato (nunca color solo):
// Postgres azul (code), Excel verde (success), CSV ambar (signal) - los
// tres tonos ya existentes del design system, sin logos de terceros.
interface FormatMeta {
  icon: typeof Database
  label: string
  iconClasses: string
  chipClasses: string
}

function formatMeta(dataset: Dataset): FormatMeta {
  if (dataset.source_type === 'postgres') {
    return {
      icon: Database,
      label: 'PostgreSQL',
      iconClasses: 'bg-code-500/10 text-code-500',
      chipClasses: 'border-code-500/30 text-code-500',
    }
  }
  if (dataset.source_extension === 'xlsx') {
    return {
      icon: FileSpreadsheet,
      label: 'XLSX',
      iconClasses: 'bg-success-500/10 text-success-500',
      chipClasses: 'border-success-500/30 text-success-500',
    }
  }
  return {
    icon: FileText,
    label: 'CSV',
    iconClasses: 'bg-signal-500/10 text-signal-500',
    chipClasses: 'border-signal-500/30 text-signal-500',
  }
}

interface DatasetCardProps {
  dataset: Dataset
  onViewSchema: (dataset: Dataset) => void
}

export function DatasetCard({ dataset, onViewSchema }: DatasetCardProps) {
  const meta = formatMeta(dataset)
  const Icon = meta.icon

  return (
    <button
      type="button"
      onClick={() => onViewSchema(dataset)}
      className="group flex flex-col gap-3 rounded-xl border border-ink-700 bg-ink-900/60 p-4 text-left transition-colors hover:border-signal-500/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${meta.iconClasses}`}>
            <Icon className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="truncate font-body text-sm font-semibold text-paper-100">{dataset.name}</p>
            <span className={`mt-0.5 inline-block rounded border px-1.5 font-mono text-[10px] leading-4 ${meta.chipClasses}`}>
              {meta.label}
            </span>
          </div>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-success-500/30 bg-success-500/10 px-2 py-0.5 font-mono text-[11px] text-success-500">
          <span className="h-1.5 w-1.5 rounded-full bg-success-500" aria-hidden="true" />
          Listo
        </span>
      </div>

      <div className="border-t border-ink-800" />

      <div className="grid grid-cols-2 gap-2 font-mono text-xs text-paper-400">
        <span className="flex items-center gap-2">
          <Rows3 className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
          {dataset.row_count.toLocaleString('es-AR')} filas
        </span>
        <span className="flex items-center gap-2">
          <Columns3 className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
          {dataset.column_count} columnas
        </span>
        <span className="col-span-2 flex items-center gap-2">
          <Clock className="h-3.5 w-3.5 text-ink-400" aria-hidden="true" />
          Actualizado: {formatDate(dataset.created_at)}
        </span>
      </div>

      <span className="font-mono text-[11px] text-signal-500 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
        Ver esquema →
      </span>
    </button>
  )
}
