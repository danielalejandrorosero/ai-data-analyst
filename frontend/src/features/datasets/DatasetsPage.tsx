import { useMe, useLogout } from '../../api/auth'
import { TraceStrip } from '../../components/TraceStrip'
import { Button } from '../../components/Button'

// Placeholder de Fase 2 (datasets) - se completa en la proxima etapa del
// frontend. Por ahora solo confirma que el login/sesion funcionan de punta
// a punta contra el backend real.
export function DatasetsPage() {
  const me = useMe()
  const logout = useLogout()
  const membership = me.data?.memberships[0]

  return (
    <div className="flex min-h-screen flex-col bg-ink-950">
      <header className="flex items-center justify-between border-b border-ink-700 px-8 py-4">
        <p className="font-mono text-sm text-signal-500">ai_data_analyst</p>
        <Button variant="ghost" onClick={logout}>
          Cerrar sesión
        </Button>
      </header>
      <main className="flex flex-1 items-center justify-center px-8">
        <div className="text-center">
          <p className="font-body text-lg text-paper-100">
            Hola, {me.data?.email ?? '…'}
          </p>
          <p className="mt-2 font-mono text-xs text-paper-400">
            Datasets y análisis se construyen en la próxima etapa.
          </p>
        </div>
      </main>
      <TraceStrip
        segments={[
          `session: authenticated`,
          `role: ${membership?.role ?? '—'}`,
          `tenant: ${membership?.organization_name ?? '—'}`,
        ]}
      />
    </div>
  )
}
