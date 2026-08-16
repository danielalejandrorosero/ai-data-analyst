import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../lib/auth-store'
import { useMe } from '../api/auth'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token)
  const me = useMe()

  if (!token) return <Navigate to="/login" replace />

  // El token existe pero todavia no confirmamos que sea valido (o ya
  // confirmamos que NO lo es, ej. expiro) - nunca renderizar la pantalla
  // protegida en ese estado intermedio/invalido (RF-002, RBAC en el
  // backend es la autoridad real, esto es solo UX).
  if (me.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-950 font-mono text-sm text-paper-400">
        cargando sesión…
      </div>
    )
  }
  if (me.isError) return <Navigate to="/login" replace />

  return <>{children}</>
}
