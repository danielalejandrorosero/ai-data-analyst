import { CircleAlert, CircleCheck, CircleX, OctagonX } from 'lucide-react'
import type { AnalysisStatus } from '../../api/analyses'
import { Button } from '../../components/Button'

const RUNNING_LABELS: Record<string, string> = {
  QUEUED: 'En cola…',
  PLANNING: 'Planificando la consulta…',
  TOOL_RUNNING: 'Ejecutando herramientas…',
  ANALYZING: 'Analizando resultados…',
  GENERATING_RESPONSE: 'Generando respuesta…',
}

interface StatusBannerProps {
  status: AnalysisStatus
  error: string | null
  onCancel: () => void
  cancelling: boolean
  canCancel: boolean
}

export function StatusBanner({ status, error, onCancel, cancelling, canCancel }: StatusBannerProps) {
  if (status === 'FAILED') {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-danger-500/30 bg-danger-500/10 px-4 py-3">
        <CircleX className="h-4 w-4 shrink-0 text-danger-500" aria-hidden="true" />
        <p className="font-mono text-xs text-danger-500">{error ?? 'El análisis falló.'}</p>
      </div>
    )
  }

  if (status === 'CANCELLED') {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-ink-600 bg-ink-900/60 px-4 py-3">
        <OctagonX className="h-4 w-4 shrink-0 text-paper-400" aria-hidden="true" />
        <p className="font-mono text-xs text-paper-400">Análisis cancelado.</p>
      </div>
    )
  }

  if (status === 'TIMED_OUT') {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-danger-500/30 bg-danger-500/10 px-4 py-3">
        <CircleAlert className="h-4 w-4 shrink-0 text-danger-500" aria-hidden="true" />
        <p className="font-mono text-xs text-danger-500">El análisis superó el tiempo máximo permitido.</p>
      </div>
    )
  }

  if (status === 'COMPLETED') {
    return (
      <div className="flex items-center gap-2 font-mono text-xs text-success-500">
        <CircleCheck className="h-3.5 w-3.5" aria-hidden="true" />
        Análisis completado
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-ink-700 bg-ink-900/60 px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="font-mono text-xs text-paper-300">{RUNNING_LABELS[status] ?? status}</span>
        {canCancel && (
          <Button variant="ghost" onClick={onCancel} loading={cancelling} className="px-2.5 py-1 text-xs">
            Cancelar
          </Button>
        )}
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-ink-800">
        <div className="h-full w-1/3 animate-progress-sweep rounded-full bg-gradient-to-r from-signal-400 to-signal-600" />
      </div>
    </div>
  )
}
