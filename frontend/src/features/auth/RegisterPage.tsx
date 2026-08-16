import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Building, Mail } from 'lucide-react'
import { useRegister } from '../../api/auth'
import { ApiError } from '../../api/client'
import { AuthLayout } from './AuthLayout'
import { Button } from '../../components/Button'
import { TextField } from '../../components/TextField'
import { PasswordField } from '../../components/PasswordField'
import { SsoDivider } from './SsoDivider'

export function RegisterPage() {
  const navigate = useNavigate()
  const register = useRegister()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [organizationName, setOrganizationName] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    register.mutate(
      { email, password, organization_name: organizationName },
      { onSuccess: () => navigate('/datasets') },
    )
  }

  const errorMessage =
    register.error instanceof ApiError
      ? register.error.status === 409
        ? 'Ese email ya está registrado.'
        : register.error.message
      : register.isError
        ? 'No se pudo conectar con el servidor.'
        : undefined

  return (
    <AuthLayout title="Crear organización" subtitle="Tu cuenta queda como OWNER de la nueva organización.">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <TextField
          label="Nombre de la organización"
          type="text"
          required
          minLength={1}
          maxLength={255}
          placeholder="Acme S.A."
          icon={<Building className="h-4 w-4" aria-hidden="true" />}
          value={organizationName}
          onChange={(e) => setOrganizationName(e.target.value)}
        />
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
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={128}
          placeholder="••••••••"
          hint="mínimo 8 caracteres"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {errorMessage && (
          <p role="alert" className="font-mono text-xs text-danger-500">
            {errorMessage}
          </p>
        )}
        <Button type="submit" loading={register.isPending} className="mt-2">
          Crear cuenta
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </form>

      <SsoDivider />

      <p className="mt-6 text-center font-body text-sm text-paper-400">
        ¿Ya tenés cuenta?{' '}
        <Link
          to="/login"
          className="rounded-sm text-signal-500 hover:text-signal-400 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950"
        >
          Iniciar sesión
        </Link>
      </p>
    </AuthLayout>
  )
}
