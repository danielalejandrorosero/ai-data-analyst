export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-xl font-bold text-signal-500" aria-hidden="true">
        [+]
      </span>
      <span className="font-body text-lg font-bold tracking-tight text-paper-100">
        Data<span className="text-signal-500">Agent</span>
      </span>
      <span className="hidden h-4 w-px bg-ink-600 sm:block" aria-hidden="true" />
      <span className="hidden font-body text-sm text-paper-400 sm:block">
        Análisis de datos con IA
      </span>
    </div>
  )
}
