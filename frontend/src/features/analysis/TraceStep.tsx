import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export type TraceStepTone = 'default' | 'success' | 'error' | 'pending'

const RING_CLASSES: Record<TraceStepTone, string> = {
  default: 'border-signal-500 text-signal-500',
  success: 'border-signal-500 text-signal-500',
  error: 'border-danger-500 text-danger-500',
  pending: 'border-ink-600 text-paper-400',
}

interface TraceStepProps {
  icon: LucideIcon
  tone?: TraceStepTone
  isLast?: boolean
  spin?: boolean
  children: ReactNode
}

// Riel vertical que conecta cada paso de la traza (inspeccion -> SQL ->
// resultado -> respuesta) con un nodo circular propio - mismo lenguaje
// visual que el mockup aprobado de la fase. El color del aro es la unica
// señal extra que agrega sobre el mockup estatico: rojo para un tool call
// en ERROR, ambar para el resto (RNF-031, un error nunca puede leerse igual
// que un paso exitoso).
export function TraceStep({ icon: Icon, tone = 'default', isLast = false, spin = false, children }: TraceStepProps) {
  return (
    <div className="flex gap-4">
      <div className="flex flex-col items-center">
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 bg-ink-950 ${RING_CLASSES[tone]}`}
        >
          <Icon className={`h-4 w-4 ${spin ? 'animate-spin' : ''}`} aria-hidden="true" />
        </span>
        {!isLast && <span className="w-px flex-1 bg-ink-700" aria-hidden="true" />}
      </div>
      <div className="flex-1 pb-4">{children}</div>
    </div>
  )
}
