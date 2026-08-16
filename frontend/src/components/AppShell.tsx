import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Database, LineChart, Link2, Settings } from 'lucide-react'
import { Logo } from './Logo'
import { TraceStrip } from './TraceStrip'
import { SystemStatus } from './SystemStatus'
import { useMe, useLogout } from '../api/auth'

const NAV_ITEMS = [
  { key: 'datasets', label: 'Datasets', icon: Database, href: '/datasets' },
  { key: 'analisis', label: 'Análisis', icon: LineChart, href: '/analisis' },
  { key: 'conexiones', label: 'Conexiones', icon: Link2, href: null },
  { key: 'configuracion', label: 'Configuración', icon: Settings, href: null },
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
    <div className="flex min-h-screen flex-col bg-ink-950">
      <header className="flex items-center justify-between border-b border-ink-700 px-8 py-4">
        <Logo />
        <button
          type="button"
          onClick={logout}
          className="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500"
          title="Cerrar sesión"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-800 font-mono text-xs font-semibold text-signal-500">
            {initials}
          </span>
          <span className="font-body text-sm text-paper-100">
            {membership?.organization_name ?? '—'}
          </span>
        </button>
      </header>

      <div className="flex flex-1">
        <nav className="w-56 shrink-0 border-r border-ink-700 px-4 py-6">
          <ul className="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              const isActive = item.key === active
              return (
                <li key={item.key}>
                  {item.href ? (
                    <Link
                      to={item.href}
                      className={`flex items-center gap-2.5 rounded-md px-3 py-2 font-body text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 ${
                        isActive ? 'bg-signal-500/10 text-signal-500' : 'text-paper-400 hover:bg-ink-900 hover:text-paper-100'
                      }`}
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                      {item.label}
                    </Link>
                  ) : (
                    <span className="flex items-center gap-2.5 rounded-md px-3 py-2 font-body text-sm text-ink-400">
                      <Icon className="h-4 w-4" aria-hidden="true" />
                      {item.label}
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
        </nav>

        <main className="flex-1 px-8 py-8">{children}</main>
      </div>

      <TraceStrip
        segments={[
          'session: authenticated',
          `role: ${membership?.role ?? '—'}`,
          `tenant: ${membership?.organization_name ?? '—'}`,
        ]}
        right={<SystemStatus />}
      />
    </div>
  )
}
