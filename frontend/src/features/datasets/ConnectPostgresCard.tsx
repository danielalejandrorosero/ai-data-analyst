import { useState, type FormEvent } from 'react'
import { ChevronDown, Database } from 'lucide-react'
import { useRegisterConnection } from '../../api/datasets'
import { ApiError } from '../../api/client'
import { Button } from '../../components/Button'
import { TextField } from '../../components/TextField'
import { PasswordField } from '../../components/PasswordField'

interface ConnectPostgresCardProps {
  organizationId: string | undefined
  token: string | null
}

export function ConnectPostgresCard({ organizationId, token }: ConnectPostgresCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [name, setName] = useState('')
  const [host, setHost] = useState('')
  const [port, setPort] = useState('5432')
  const [databaseName, setDatabaseName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const register = useRegisterConnection(organizationId, token)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    register.mutate({
      type: 'postgres',
      name,
      host,
      port: Number(port),
      database_name: databaseName,
      username,
      password,
    })
  }

  const errorMessage =
    register.error instanceof ApiError ? register.error.message : register.isError ? 'No se pudo conectar con el servidor.' : undefined

  return (
    <div className="rounded-xl border border-ink-700 bg-ink-900/60">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
      >
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-ink-800 text-signal-500">
            <Database className="h-4.5 w-4.5" aria-hidden="true" />
          </span>
          <div>
            <p className="font-body text-sm font-semibold text-paper-100">Conectar PostgreSQL externo</p>
            <p className="font-body text-xs text-paper-400">Conectá una base de datos PostgreSQL externa</p>
          </div>
        </div>
        <ChevronDown
          className={`h-4 w-4 text-paper-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>

      {expanded && (
        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4 border-t border-ink-700 p-4">
          <TextField
            label="Nombre de la conexión"
            required
            placeholder="analytics_prod"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-[2fr_1fr]">
            <TextField label="Host" required placeholder="db.acme.com" value={host} onChange={(e) => setHost(e.target.value)} />
            <TextField
              label="Puerto"
              type="number"
              required
              value={port}
              onChange={(e) => setPort(e.target.value)}
            />
          </div>
          <TextField
            label="Base de datos"
            required
            placeholder="analytics_prod"
            value={databaseName}
            onChange={(e) => setDatabaseName(e.target.value)}
          />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <TextField
              label="Usuario"
              required
              placeholder="readonly_user"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <PasswordField label="Contraseña" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {errorMessage && (
            <p role="alert" className="font-mono text-xs text-danger-500">
              {errorMessage}
            </p>
          )}
          {register.isSuccess && (
            <p className="font-mono text-xs text-success-500">Conexión "{register.data.name}" verificada y guardada.</p>
          )}
          <Button type="submit" loading={register.isPending} className="self-start">
            Conectar
          </Button>
        </form>
      )}
    </div>
  )
}
