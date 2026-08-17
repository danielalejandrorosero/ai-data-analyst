import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Database, FileText, LineChart, Link2, Settings } from 'lucide-react'
import { Logo } from './Logo'
import { DotGridGlow } from './DotGridGlow'
import { TraceStrip } from './TraceStrip'
import { SystemStatus } from './SystemStatus'
import { useMe, useLogout } from '../api/auth'

const NAV_ITEMS = [
  { key: 'datasets', label: 'Datasets', icon: Database, href: '/datasets' },
  { key: 'analisis', label: 'Análisis', icon: LineChart, href: '/analisis' },
  { key: 'documentos', label: 'Documentos', icon: FileText, href: '/documentos' },
  { key: 'conexiones', label: 'Conexiones', icon: Link2, href: '/conexiones' },
  { key: 'configuracion', label: 'Configuración', icon: Settings, href: '/configuracion' },
] as const

interface AppShellProps {
  active: (typeof NAV_ITEMS)[number]['key']
  children: ReactNode
}

export function AppShell({ active, children }: AppShellProps) {
  const me = useMe()
  const logout = useLogout()
  const membership = me.data?.memberships[0]
  const initials = (me.data?.email ?? '??').slice(0, 2).toUpperCase()

  return (
    <div className="relative flex h-screen flex-col overflow-hidden bg-ink-950">
      <DotGridGlow />
      <header className="relative z-10 flex items-center justify-between border-b border-ink-700 px-4 py-4 md:px-8">
        <Logo />
        <button
          type="button"
          onClick={logout}
          className="flex min-w-0 items-center gap-2 rounded-md px-2 py-1 hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
          title="Cerrar sesión"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-800 font-mono text-xs font-semibold text-signal-500">
            {initials}
          </span>
          <span className="hidden max-w-[10rem] truncate font-body text-sm text-paper-100 sm:inline md:max-w-none">
            {membership?.organization_name ?? '—'}
          </span>
        </button>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1">
        <nav className="w-16 shrink-0 overflow-y-auto border-r border-ink-700 px-2 py-6 lg:w-56 lg:px-4">
          <ul className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = item.key === active
              return (
                <li key={item.key}>
                  <Link
                    to={item.href}
                    aria-label={item.label}
                    title={item.label}
                    className={`flex items-center justify-center gap-2.5 rounded-md px-3 py-2 font-body text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 lg:justify-start ${
                      isActive ? 'bg-signal-500/10 text-signal-500' : 'text-paper-400 hover:bg-ink-900 hover:text-paper-100'
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span className="hidden lg:inline">{item.label}</span>
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>

      <div className="relative z-10">
        <TraceStrip
          segments={[
            'session: authenticated',
            `role: ${membership?.role ?? '—'}`,
            `tenant: ${membership?.organization_name ?? '—'}`,
          ]}
          right={<SystemStatus />}
        />
      </div>
    </div>
  )
}
