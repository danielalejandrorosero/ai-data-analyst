import { useState, type FormEvent } from 'react'
import { Building, CheckCircle2, KeyRound, Mail, ShieldCheck } from 'lucide-react'
import { useChangePassword, useMe } from '../../api/auth'
import { ApiError } from '../../api/client'
import { AppShell } from '../../components/AppShell'
import { PasswordField } from '../../components/PasswordField'
import { Button } from '../../components/Button'

const ROLE_LABELS: Record<string, string> = {
  OWNER: 'Owner',
  ADMIN: 'Admin',
  ANALYST: 'Analista',
  VIEWER: 'Viewer',
}

export function SettingsPage() {
  const me = useMe()
  const membership = me.data?.memberships[0]
  const changePassword = useChangePassword()

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [mismatchError, setMismatchError] = useState(false)

  function resetForm() {
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    changePassword.reset()

    if (newPassword !== confirmPassword) {
      setMismatchError(true)
      return
    }
    setMismatchError(false)

    changePassword.mutate(
      { current_password: currentPassword, new_password: newPassword },
      { onSuccess: () => resetForm() },
    )
  }

  const serverError =
    changePassword.error instanceof ApiError
      ? changePassword.error.message
      : changePassword.isError
        ? 'No se pudo conectar con el servidor.'
        : undefined

  return (
    <AppShell active="configuracion">
      <div className="mb-6">
        <h1 className="font-body text-3xl font-bold text-paper-100">Configuración</h1>
        <p className="mt-1 font-body text-sm text-paper-400">Tu cuenta y credenciales de acceso</p>
      </div>

      <div className="flex flex-col gap-6 lg:max-w-xl">
        <section
          aria-labelledby="account-section-title"
          className="rounded-xl border border-ink-700 bg-ink-900/40 p-6"
        >
          <h2
            id="account-section-title"
            className="mb-4 flex items-center gap-2 font-body text-lg font-semibold text-paper-100"
          >
            <ShieldCheck className="h-4 w-4 text-signal-500" aria-hidden="true" />
            Tu cuenta
          </h2>

          {me.isPending && (
            <p className="font-mono text-sm text-paper-400">cargando…</p>
          )}

          {me.isError && (
            <p role="alert" className="font-mono text-sm text-danger-500">
              No se pudo cargar la información de la cuenta.
            </p>
          )}

          {me.data && (
            <dl className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <Mail className="h-4 w-4 shrink-0 text-paper-400" aria-hidden="true" />
                <div>
                  <dt className="font-mono text-xs text-paper-400">Email</dt>
                  <dd className="font-body text-sm text-paper-100">{me.data.email}</dd>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-4 w-4 shrink-0 text-paper-400" aria-hidden="true" />
                <div>
                  <dt className="font-mono text-xs text-paper-400">Rol</dt>
                  <dd className="font-body text-sm text-paper-100">
                    {membership ? (ROLE_LABELS[membership.role] ?? membership.role) : '—'}
                  </dd>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Building className="h-4 w-4 shrink-0 text-paper-400" aria-hidden="true" />
                <div>
                  <dt className="font-mono text-xs text-paper-400">Organización</dt>
                  <dd className="font-body text-sm text-paper-100">
                    {membership?.organization_name ?? '—'}
                  </dd>
                </div>
              </div>
            </dl>
          )}
        </section>

        <section
          aria-labelledby="password-section-title"
          className="rounded-xl border border-ink-700 bg-ink-900/40 p-6"
        >
          <h2
            id="password-section-title"
            className="mb-4 flex items-center gap-2 font-body text-lg font-semibold text-paper-100"
          >
            <KeyRound className="h-4 w-4 text-signal-500" aria-hidden="true" />
            Cambiar contraseña
          </h2>

          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
            <PasswordField
              label="Contraseña actual"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <PasswordField
              label="Contraseña nueva"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              hint="mínimo 8 caracteres"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <PasswordField
              label="Confirmar contraseña nueva"
              autoComplete="new-password"
              required
              value={confirmPassword}
              error={mismatchError ? 'Las contraseñas nuevas no coinciden.' : undefined}
              onChange={(e) => {
                setConfirmPassword(e.target.value)
                if (mismatchError) setMismatchError(false)
              }}
            />

            {serverError && (
              <p role="alert" className="font-mono text-xs text-danger-500">
                {serverError}
              </p>
            )}

            {changePassword.isSuccess && (
              <p className="flex items-center gap-1.5 font-mono text-xs text-success-500">
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                Contraseña actualizada correctamente.
              </p>
            )}

            <Button type="submit" loading={changePassword.isPending} className="mt-2 self-start">
              Guardar contraseña
            </Button>
          </form>
        </section>
      </div>
    </AppShell>
  )
}
