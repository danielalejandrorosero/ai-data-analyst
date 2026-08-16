import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Mail } from 'lucide-react'
import { useLogin } from '../../api/auth'
import { ApiError } from '../../api/client'
import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/Button'
import { TextField } from '../../components/TextField'
import { PasswordField } from '../../components/PasswordField'
import { SsoDivider } from './SsoDivider'

export function LoginPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    login.mutate(
      { email, password },
      { onSuccess: () => navigate('/datasets') },
    )
  }

  const errorMessage =
    login.error instanceof ApiError
      ? login.error.status === 401
        ? 'Email o contraseña incorrectos.'
        : login.error.message
      : login.isError
        ? 'No se pudo conectar con el servidor.'
        : undefined

  return (
    <AuthLayout title="Iniciar sesión" subtitle="Entrá con tu cuenta de la organización.">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          required
          placeholder="tu@empresa.com"
          icon={<Mail className="h-4 w-4" aria-hidden="true" />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <PasswordField
          label="Contraseña"
          autoComplete="current-password"
          required
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {errorMessage && (
          <p role="alert" className="font-mono text-xs text-danger-500">
            {errorMessage}
          </p>
        )}
        <Button type="submit" loading={login.isPending} className="mt-2">
          Entrar
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </form>

      <p className="mt-4 text-center font-body text-sm text-ink-400">¿Olvidaste la contraseña?</p>

      <SsoDivider />

      <p className="mt-6 text-center font-body text-sm text-paper-400">
        ¿No tenés cuenta?{' '}
        <Link
          to="/register"
          className="rounded-sm text-signal-500 hover:text-signal-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950"
        >
          Creá una organización
        </Link>
      </p>
    </AuthLayout>
  )
}
