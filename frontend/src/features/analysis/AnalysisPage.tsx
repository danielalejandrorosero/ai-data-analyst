import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PackageOpen, Sparkles } from 'lucide-react'
import { useMe } from '../../api/auth'
import { useAuthStore } from '../../lib/auth-store'
import { useDatasets } from '../../api/datasets'
import { useAnalyses, useCreateAnalysis } from '../../api/analyses'
import { AppShell } from '../../components/AppShell'
import { DatasetSelector } from './DatasetSelector'
import { AnalysisHistoryList } from './AnalysisHistoryList'
import { AnalysisRunCard } from './AnalysisRunCard'
import { QuestionInput } from './QuestionInput'

export function AnalysisPage() {
  const token = useAuthStore((s) => s.token)
  const me = useMe()
  const membership = me.data?.memberships[0]
  const datasets = useDatasets(membership?.organization_id, token)
  const analyses = useAnalyses(membership?.organization_id, token)
  const createAnalysis = useCreateAnalysis(membership?.organization_id, token)

  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const [activeAnalysisId, setActiveAnalysisId] = useState<string | null>(null)

  const canAnalyze = membership && ['OWNER', 'ADMIN', 'ANALYST'].includes(membership.role)

  // Preselecciona el primer dataset disponible apenas carga la lista, y el
  // analisis mas reciente del historial (si hay) para no arrancar en blanco.
  useEffect(() => {
    if (!selectedDatasetId && datasets.data && datasets.data.length > 0) {
      setSelectedDatasetId(datasets.data[0].id)
    }
  }, [datasets.data, selectedDatasetId])

  useEffect(() => {
    if (!activeAnalysisId && analyses.data && analyses.data.length > 0) {
      setActiveAnalysisId(analyses.data[0].id)
    }
  }, [analyses.data, activeAnalysisId])

  function handleAsk(question: string) {
    if (!selectedDatasetId) return
    createAnalysis.mutate(
      { datasetId: selectedDatasetId, question },
      { onSuccess: (analysis) => setActiveAnalysisId(analysis.id) },
    )
  }

  return (
    <AppShell active="analisis">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-body text-3xl font-bold text-paper-100">Análisis</h1>
          <p className="mt-1 font-body text-sm text-paper-400">Trazabilidad completa de la consulta sobre el dataset activo</p>
        </div>
        {datasets.data && (
          <DatasetSelector datasets={datasets.data} value={selectedDatasetId} onChange={setSelectedDatasetId} />
        )}
      </div>

      {datasets.data && datasets.data.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-ink-700 bg-ink-900/40 py-16 text-center">
          <PackageOpen className="h-8 w-8 text-ink-400" aria-hidden="true" />
          <p className="font-body text-sm text-paper-400">Todavía no hay datasets para analizar.</p>
          <Link
            to="/datasets"
            className="font-body text-sm font-semibold text-signal-500 hover:text-signal-400"
          >
            Importar un dataset →
          </Link>
        </div>
      )}

      {datasets.data && datasets.data.length > 0 && (
        <div className="flex gap-6">
          <AnalysisHistoryList
            analyses={analyses.data ?? []}
            activeId={activeAnalysisId}
            onSelect={setActiveAnalysisId}
          />

          <div className="flex flex-1 flex-col gap-4">
            {activeAnalysisId ? (
              <AnalysisRunCard analysisId={activeAnalysisId} token={token} canCancel={!!canAnalyze} />
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-ink-700 bg-ink-900/40 py-16 text-center">
                <Sparkles className="h-8 w-8 text-ink-400" aria-hidden="true" />
                <p className="font-body text-sm text-paper-400">Hacé tu primera pregunta sobre este dataset.</p>
              </div>
            )}

            {canAnalyze ? (
              <QuestionInput
                disabled={!selectedDatasetId}
                submitting={createAnalysis.isPending}
                onSubmit={handleAsk}
              />
            ) : (
              <p className="font-mono text-xs text-paper-400">
                Tu rol ({membership?.role}) no tiene permiso para ejecutar análisis.
              </p>
            )}

            {createAnalysis.isError && (
              <p role="alert" className="font-mono text-xs text-danger-500">
                No se pudo iniciar el análisis.
              </p>
            )}
          </div>
        </div>
      )}
    </AppShell>
  )
}
