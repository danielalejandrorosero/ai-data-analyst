import { Calendar, Clock, Database, Wifi, WifiOff } from 'lucide-react'
import { useHealthStatus } from '../api/health'
import { useClock } from '../lib/use-clock'

function formatTime(date: Date): string {
  return date.toLocaleTimeString('es-AR', { hour12: false })
}

function formatDate(date: Date): string {
  return date.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function SystemStatus() {
  const health = useHealthStatus()
  const now = useClock()

  const apiOnline = health.data?.status === 'ok'
  const dbReady = health.data?.checks?.database === 'ok'

  return (
    <div className="flex items-center gap-4 font-mono text-xs text-paper-400">
      <span className="flex items-center gap-1.5">
        {apiOnline ? (
          <Wifi className="h-3.5 w-3.5 text-success-500" aria-hidden="true" />
        ) : (
          <WifiOff className="h-3.5 w-3.5 text-danger-500" aria-hidden="true" />
        )}
        API {apiOnline ? 'online' : 'offline'}
      </span>
      <span className="flex items-center gap-1.5">
        <Database className={`h-3.5 w-3.5 ${dbReady ? 'text-success-500' : 'text-danger-500'}`} aria-hidden="true" />
        DB {dbReady ? 'ready' : 'down'}
      </span>
      <span className="flex items-center gap-1.5">
        <Clock className="h-3.5 w-3.5" aria-hidden="true" />
        {formatTime(now)}
      </span>
      <span className="hidden items-center gap-1.5 sm:flex">
        <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
        {formatDate(now)}
      </span>
    </div>
  )
}
