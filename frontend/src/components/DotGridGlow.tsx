// Fondo decorativo: grilla de puntos + resplandor ambar difuminado en la
// esquina. Puramente visual, no debe interferir con el contenido real.
export function DotGridGlow() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute inset-0 opacity-50"
        style={{
          backgroundImage: 'radial-gradient(var(--color-ink-700) 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />
      <div className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-signal-500/25 blur-[110px]" />
    </div>
  )
}
