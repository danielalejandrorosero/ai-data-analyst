import type { ReactNode } from 'react'
import { Terminal } from 'lucide-react'
import { TraceStrip } from '../../components/TraceStrip'
import { SystemStatus } from '../../components/SystemStatus'
import { DotGridGlow } from '../../components/DotGridGlow'
import { AuthHeader } from './AuthHeader'
import { TerminalIntro } from './TerminalIntro'
import { FeatureBadges } from './FeatureBadges'
import { TerminalPreviewCard } from './TerminalPreviewCard'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
}

// Split 50/50 real (como la referencia): las dos columnas comparten la fila
// en partes iguales desde lg, separadas por una linea simple. El bloque de
// codigo/tabla dentro de TerminalPreviewCard tiene su propio breakpoint mas
// alto (min-[1600px]) para no intentar partirse en dos columnas internas
// hasta que la mitad del hero realmente tenga sitio para eso.
export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen flex-col overflow-hidden bg-ink-950">
      <DotGridGlow />
      <AuthHeader />

      <div className="relative z-10 flex w-full flex-1 flex-col lg:flex-row">
        <div className="flex flex-1 flex-col justify-center gap-8 px-8 py-12 md:px-12 lg:border-r lg:border-ink-700 lg:px-16 lg:py-16">
          <TerminalIntro />
          <FeatureBadges />
          <TerminalPreviewCard />
        </div>

        <div className="flex flex-1 items-center justify-center px-8 py-12 lg:px-16 lg:py-16">
          <div className="min-h-[700px] w-full max-w-xl rounded-2xl border border-ink-700 bg-ink-900/60 p-10">
            <div className="flex flex-col items-center text-center">
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-signal-400 to-signal-600 text-ink-950">
                <Terminal className="h-7 w-7" strokeWidth={2} aria-hidden="true" />
              </span>
              <h2 className="mt-4 font-body text-xl font-bold text-paper-100">{title}</h2>
              <p className="mt-1 font-body text-sm text-paper-400">{subtitle}</p>
            </div>
            <div className="mt-8">{children}</div>
          </div>
        </div>
      </div>

      <TraceStrip
        segments={['session: unauthenticated', 'role: —', 'tenant: —']}
        right={<SystemStatus />}
      />
    </div>
  )
}
