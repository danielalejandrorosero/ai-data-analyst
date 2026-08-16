import { CircleCheck, Loader2 } from 'lucide-react'
import {
  isTerminalStatus,
  useAnalysis,
  useAnalysisArtifacts,
  useAnalysisEventStream,
  useCancelAnalysis,
  useExportAnalysis,
} from '../../api/analyses'
import { pairToolCallsWithResults } from './toolTrace'
import { ToolCallBlock } from './ToolCallBlock'
import { StatusBanner } from './StatusBanner'

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
}

interface AnalysisRunCardProps {
  analysisId: string
  token: string | null
  canCancel: boolean
}

export function AnalysisRunCard({ analysisId, token, canCancel }: AnalysisRunCardProps) {
  const analysisQuery = useAnalysis(analysisId, token)
  const analysis = analysisQuery.data
  const isTerminal = analysis ? isTerminalStatus(analysis.status) : false

  useAnalysisEventStream(analysisId, token, !isTerminal)
  const artifactsQuery = useAnalysisArtifacts(analysisId, token)
  const cancel = useCancelAnalysis(token)
  const exportMutation = useExportAnalysis()

  if (analysisQuery.isPending) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-900/60 px-4 py-6 font-mono text-xs text-paper-400">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        cargando análisis…
      </div>
    )
  }

  if (analysisQuery.isError || !analysis) {
    return (
      <p role="alert" className="rounded-lg border border-danger-500/30 bg-danger-500/10 px-4 py-3 font-mono text-xs text-danger-500">
        No se pudo cargar este análisis.
      </p>
    )
  }

  const traced = pairToolCallsWithResults(analysis)
  const artifacts = artifactsQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <div className="max-w-2xl rounded-2xl rounded-tr-sm bg-signal-500/10 px-4 py-3">
          <p className="font-body text-sm text-paper-100">{analysis.question}</p>
          <p className="mt-1 text-right font-mono text-[10px] text-paper-400">{formatTime(analysis.created_at)}</p>
        </div>
      </div>

      {traced.map((t) => (
        <ToolCallBlock
          key={t.index}
          traced={t}
          artifacts={artifacts}
          exporting={exportMutation.isPending}
          onExport={(queryIndex, format) =>
            exportMutation.mutate({ analysisId, token, format, queryIndex })
          }
        />
      ))}

      {!isTerminal || analysis.status !== 'COMPLETED' ? (
        <StatusBanner
          status={analysis.status}
          error={analysis.error}
          onCancel={() => cancel.mutate(analysisId)}
          cancelling={cancel.isPending}
          canCancel={canCancel}
        />
      ) : null}

      {analysis.answer && (
        <div className="rounded-lg border border-signal-500/30 bg-signal-500/5 p-4">
          <div className="mb-2 flex items-center gap-2">
            <CircleCheck className="h-4 w-4 text-signal-500" aria-hidden="true" />
            <p className="font-body text-sm font-semibold text-paper-100">Respuesta</p>
          </div>
          <p className="whitespace-pre-wrap font-body text-sm leading-relaxed text-paper-300">{analysis.answer}</p>
        </div>
      )}
    </div>
  )
}
