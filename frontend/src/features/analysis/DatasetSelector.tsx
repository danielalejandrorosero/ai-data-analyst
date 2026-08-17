import { ChevronDown, Database } from 'lucide-react'
import type { Dataset } from '../../api/datasets'

interface DatasetSelectorProps {
  datasets: Dataset[]
  value: string | null
  onChange: (datasetId: string) => void
}

export function DatasetSelector({ datasets, value, onChange }: DatasetSelectorProps) {
  if (datasets.length === 0) return null

  return (
    <div className="relative">
      <Database
        className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-paper-400"
        aria-hidden="true"
      />
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Dataset activo"
        className="appearance-none rounded-md border border-ink-600 bg-ink-900 py-2 pr-9 pl-9 font-body text-sm text-paper-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
      >
        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {dataset.name}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute top-1/2 right-3 h-4 w-4 -translate-y-1/2 text-paper-400"
        aria-hidden="true"
      />
    </div>
  )
}
