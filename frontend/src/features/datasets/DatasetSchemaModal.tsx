import { useEffect } from 'react'
import { X } from 'lucide-react'
import { useDatasetSchema } from '../../api/datasets'

interface DatasetSchemaModalProps {
  datasetId: string
  onClose: () => void
  token: string | null
}

export function DatasetSchemaModal({ datasetId, onClose, token }: DatasetSchemaModalProps) {
  const schema = useDatasetSchema(datasetId, token)

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/70 p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dataset-schema-title"
        onClick={(e) => e.stopPropagation()}
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl border border-ink-700 bg-ink-900 p-6"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="dataset-schema-title" className="font-body text-lg font-bold text-paper-100">
            {schema.data?.name ?? 'Esquema del dataset'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm p-1 text-paper-400 hover:text-paper-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
            aria-label="Cerrar"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {schema.isPending && <p className="font-mono text-sm text-paper-400">cargando esquema…</p>}
        {schema.isError && <p className="font-mono text-sm text-danger-500">No se pudo cargar el esquema.</p>}

        {schema.data && (
          <>
            <p className="mb-3 font-mono text-xs text-paper-400">
              {schema.data.row_count.toLocaleString('es-AR')} filas · {schema.data.columns.length} columnas
            </p>
            <div className="overflow-hidden rounded-md border border-ink-700">
              <table className="w-full font-mono text-xs">
                <thead>
                  <tr className="border-b border-ink-700 bg-ink-800 text-paper-400">
                    <th className="px-3 py-2 text-left font-medium">columna</th>
                    <th className="px-3 py-2 text-left font-medium">tipo</th>
                  </tr>
                </thead>
                <tbody>
                  {schema.data.columns.map((col) => (
                    <tr key={col.name} className="border-b border-ink-800 text-paper-300">
                      <td className="px-3 py-2">{col.name}</td>
                      <td className="px-3 py-2 text-code-500">{col.type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
