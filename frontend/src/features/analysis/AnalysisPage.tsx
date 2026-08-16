import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { PackageOpen, Sparkles } from 'lucide-react'
import { useMe } from '../../api/auth'
import { useAuthStore } from '../../lib/auth-store'
import { useDatasets } from '../../api/datasets'
import { useAnalyses, useCreateAnalysis } from '../../api/analyses'
import { AppShell } from '../../components/AppShell'
import { DatasetSelector } from './DatasetSelector'
import { DatasetChatList } from './DatasetChatList'
import { AnalysisRunCard } from './AnalysisRunCard'
import { QuestionInput } from './QuestionInput'

// Tope de mensajes renderizados por hilo: cada AnalysisRunCard trae su
// propio detalle/artifacts, y un chat con cientos de analisis viejos no
// aporta nada visible - los mas antiguos siguen existiendo en la API.
const MAX_RENDERED = 20

export function AnalysisPage() {
  const token = useAuthStore((s) => s.token)
  const me = useMe()
  const membership = me.data?.memberships[0]
  const datasets = useDatasets(membership?.organization_id, token)
  const analyses = useAnalyses(membership?.organization_id, token)
  const createAnalysis = useCreateAnalysis(membership?.organization_id, token)

  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const canAnalyze = membership && ['OWNER', 'ADMIN', 'ANALYST'].includes(membership.role)

  useEffect(() => {
    if (!selectedDatasetId && datasets.data && datasets.data.length > 0) {
      setSelectedDatasetId(datasets.data[0].id)
    }
  }, [datasets.data, selectedDatasetId])

  // El hilo del dataset activo, en orden cronologico (chat que baja) - la
  // API lista mas recientes primero, aca se invierte.
  const thread = useMemo(() => {
    const own = (analyses.data ?? []).filter((a) => a.dataset_id === selectedDatasetId)
    return own.slice().reverse()
  }, [analyses.data, selectedDatasetId])
  const visibleThread = thread.slice(-MAX_RENDERED)

  // Chat: al agregar un mensaje al hilo, ir al final; al cambiar de hilo,
  // saltar directo sin animacion.
  const previousDataset = useRef<string | null>(null)
  useEffect(() => {
    const switched = previousDataset.current !== selectedDatasetId
    previousDataset.current = selectedDatasetId
    bottomRef.current?.scrollIntoView({ behavior: switched ? 'instant' : 'smooth', block: 'end' })
  }, [selectedDatasetId, thread.length])

  function handleAsk(question: string) {
    if (!selectedDatasetId) return
    createAnalysis.mutate({ datasetId: selectedDatasetId, question })
  }

  return (
    <AppShell active="analisis">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-body text-3xl font-bold text-paper-100">Análisis</h1>
          <p className="mt-1 font-body text-sm text-paper-400">
            Un chat por dataset, con trazabilidad completa de cada consulta
          </p>
        </div>
        {datasets.data && (
          <DatasetSelector datasets={datasets.data} value={selectedDatasetId} onChange={setSelectedDatasetId} />
        )}
      </div>

      {datasets.data && datasets.data.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-ink-700 bg-ink-900/40 py-16 text-center">
          <PackageOpen className="h-8 w-8 text-ink-400" aria-hidden="true" />
          <p className="font-body text-sm text-paper-400">Todavía no hay datasets para analizar.</p>
          <Link to="/datasets" className="font-body text-sm font-semibold text-signal-500 hover:text-signal-400">
            Importar un dataset →
          </Link>
        </div>
      )}

      {datasets.data && datasets.data.length > 0 && (
        <div className="flex gap-6">
          <DatasetChatList
            datasets={datasets.data}
            analyses={analyses.data ?? []}
            activeDatasetId={selectedDatasetId}
            onSelect={setSelectedDatasetId}
          />

          <div className="flex min-w-0 flex-1 flex-col gap-6">
            {thread.length > visibleThread.length && (
              <p className="text-center font-mono text-xs text-ink-400">
                Mostrando los últimos {MAX_RENDERED} de {thread.length} análisis de este chat
              </p>
            )}

            {visibleThread.length === 0 && (
              <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-ink-700 bg-ink-900/40 py-16 text-center">
                <Sparkles className="h-8 w-8 text-ink-400" aria-hidden="true" />
                <p className="font-body text-sm text-paper-400">Hacé tu primera pregunta sobre este dataset.</p>
              </div>
            )}

            {visibleThread.map((analysis) => (
              <AnalysisRunCard
                key={analysis.id}
                analysisId={analysis.id}
                token={token}
                canCancel={!!canAnalyze}
              />
            ))}

            <div ref={bottomRef} aria-hidden="true" />

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
