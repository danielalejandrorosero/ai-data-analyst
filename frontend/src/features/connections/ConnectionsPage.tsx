import { Database, Link2, Loader2, ShieldCheck } from 'lucide-react'
import { useMe } from '../../api/auth'
import { useAuthStore } from '../../lib/auth-store'
import { useConnections } from '../../api/datasets'
import { AppShell } from '../../components/AppShell'
import { ConnectPostgresCard } from './ConnectPostgresCard'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ConnectionsPage() {
  const token = useAuthStore((s) => s.token)
  const me = useMe()
  const membership = me.data?.memberships[0]
  const connections = useConnections(membership?.organization_id, token)

  const canConnect = membership && ['OWNER', 'ADMIN'].includes(membership.role)

  return (
    <AppShell active="conexiones">
      <div className="mb-6">
        <h1 className="font-body text-3xl font-bold text-paper-100">Conexiones</h1>
        <p className="mt-1 font-body text-sm text-paper-400">
          Fuentes de datos externas conectadas a esta organización
        </p>
      </div>

      {connections.isPending && (
        <div className="flex items-center gap-2 py-12 font-mono text-sm text-paper-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          cargando conexiones…
        </div>
      )}

      {connections.isError && (
        <p role="alert" className="font-mono text-sm text-danger-500">
          No se pudieron cargar las conexiones.
        </p>
      )}

      {connections.data && connections.data.length > 0 && (
        <div className="mb-6 flex flex-col gap-4">
          {connections.data.map((connection) => (
            <div
              key={connection.id}
              className="flex flex-col gap-4 rounded-xl border border-ink-700 bg-ink-900/60 p-5"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-9 w-9 items-center justify-center rounded-md bg-code-500/10 text-code-500">
                    <Database className="h-4.5 w-4.5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="font-body text-sm font-semibold text-paper-100">{connection.name}</p>
                    <span className="mt-0.5 inline-block rounded border border-code-500/30 px-1.5 font-mono text-[10px] leading-4 text-code-500">
                      PostgreSQL
                    </span>
                  </div>
                </div>
                <span className="flex shrink-0 items-center gap-1.5 rounded-full border border-success-500/30 bg-success-500/10 px-2 py-0.5 font-mono text-[11px] text-success-500">
                  <span className="h-1.5 w-1.5 rounded-full bg-success-500" aria-hidden="true" />
                  {connection.status === 'active' ? 'Activa' : connection.status}
                </span>
              </div>

              <div className="border-t border-ink-800" />

              <dl className="grid grid-cols-1 gap-3 font-mono text-xs text-paper-400 sm:grid-cols-2">
                <div>
                  <dt className="text-ink-400">Host</dt>
                  <dd className="mt-0.5 text-paper-100">{connection.host}</dd>
                </div>
                <div>
                  <dt className="text-ink-400">Puerto</dt>
                  <dd className="mt-0.5 text-paper-100">{connection.port}</dd>
                </div>
                <div>
                  <dt className="text-ink-400">Base de datos</dt>
                  <dd className="mt-0.5 text-paper-100">{connection.database_name}</dd>
                </div>
                <div>
                  <dt className="text-ink-400">Usuario</dt>
                  <dd className="mt-0.5 text-paper-100">{connection.username}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-ink-400">Conectada</dt>
                  <dd className="mt-0.5 text-paper-100">{formatDate(connection.created_at)}</dd>
                </div>
              </dl>
            </div>
          ))}

          <p className="flex items-center gap-2 font-mono text-xs text-ink-400">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            El MVP soporta una única conexión externa por organización.
          </p>
        </div>
      )}

      {connections.data && connections.data.length === 0 && (
        <div className="mb-6 flex flex-col items-center gap-2 rounded-xl border border-ink-700 bg-ink-900/40 py-12 text-center">
          <Link2 className="h-8 w-8 text-ink-400" aria-hidden="true" />
          <p className="font-body text-sm text-paper-400">Todavía no hay ninguna conexión registrada.</p>
        </div>
      )}

      {connections.data && connections.data.length === 0 && canConnect && (
        <div className="max-w-xl">
          <ConnectPostgresCard organizationId={membership?.organization_id} token={token} />
        </div>
      )}
    </AppShell>
  )
}
