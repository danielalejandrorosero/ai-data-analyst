import { useState } from 'react'
import { Loader2, PackageOpen } from 'lucide-react'
import { useMe } from '../../api/auth'
import { useAuthStore } from '../../lib/auth-store'
import { useDatasets } from '../../api/datasets'
import { AppShell } from '../../components/AppShell'
import { DatasetCard } from './DatasetCard'
import { UploadDropzone } from './UploadDropzone'
import { DatasetSchemaModal } from './DatasetSchemaModal'

export function DatasetsPage() {
  const token = useAuthStore((s) => s.token)
  const me = useMe()
  const membership = me.data?.memberships[0]
  const datasets = useDatasets(membership?.organization_id, token)
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)

  const canImport = membership && ['OWNER', 'ADMIN', 'ANALYST'].includes(membership.role)

  return (
    <AppShell active="datasets">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="flex items-baseline gap-2.5 font-body text-3xl font-bold text-paper-100">
            Datasets
            {datasets.data && (
              <span className="font-mono text-sm font-normal text-paper-400">
                {datasets.data.length} activo{datasets.data.length === 1 ? '' : 's'}
              </span>
            )}
          </h1>
          <p className="mt-1 font-body text-sm text-paper-400">
            Fuentes de datos disponibles para consultar
          </p>
        </div>
      </div>

      {datasets.isPending && (
        <div className="flex items-center gap-2 py-12 font-mono text-sm text-paper-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          cargando datasets…
        </div>
      )}

      {datasets.isError && (
        <p role="alert" className="font-mono text-sm text-danger-500">
          No se pudieron cargar los datasets.
        </p>
      )}

      {datasets.data && datasets.data.length > 0 && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {datasets.data.map((dataset) => (
            <DatasetCard key={dataset.id} dataset={dataset} onViewSchema={(d) => setSelectedDatasetId(d.id)} />
          ))}
        </div>
      )}

      {datasets.data && datasets.data.length === 0 && (
        <div className="mb-6 flex flex-col items-center gap-2 rounded-xl border border-ink-700 bg-ink-900/40 py-12 text-center">
          <PackageOpen className="h-8 w-8 text-ink-400" aria-hidden="true" />
          <p className="font-body text-sm text-paper-400">Todavía no hay datasets importados.</p>
        </div>
      )}

      {canImport && (
        <div className="max-w-xl">
          <UploadDropzone organizationId={membership?.organization_id} token={token} />
        </div>
      )}

      {selectedDatasetId && (
        <DatasetSchemaModal datasetId={selectedDatasetId} token={token} onClose={() => setSelectedDatasetId(null)} />
      )}
    </AppShell>
  )
}
