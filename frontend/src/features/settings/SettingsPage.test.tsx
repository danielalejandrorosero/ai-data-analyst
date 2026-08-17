import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/render'
import { SettingsPage } from './SettingsPage'
import { useAuthStore } from '../../lib/auth-store'
import type { User } from '../../api/types'

const ME: User = {
  id: 'user-1',
  email: 'ana@acme.com',
  status: 'active',
  memberships: [{ organization_id: 'org-1', organization_name: 'Acme S.A.', role: 'ANALYST' }],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function installFetchMock(opts: { changePasswordStatus?: number; changePasswordDetail?: string }) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = init?.method ?? 'GET'

    if (url.includes('/auth/me/password') && method === 'PATCH') {
      const status = opts.changePasswordStatus ?? 204
      if (status === 204) {
        return Promise.resolve(new Response(null, { status: 204 }))
      }
      return Promise.resolve(
        jsonResponse({ detail: opts.changePasswordDetail ?? 'Error' }, status),
      )
    }
    if (url.includes('/auth/me')) {
      return Promise.resolve(jsonResponse(ME))
    }
    throw new Error(`Unhandled fetch in test: ${url}`)
  })
}

describe('SettingsPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'test-token' })
    vi.restoreAllMocks()
  })

  it('shows the real email, role and organization of the current user', async () => {
    installFetchMock({})
    renderWithProviders(<SettingsPage />)

    expect(await screen.findByText('ana@acme.com')).toBeInTheDocument()
    const accountSection = screen.getByRole('heading', { name: 'Tu cuenta' }).closest('section')!
    expect(within(accountSection).getByText('Analista')).toBeInTheDocument()
    expect(within(accountSection).getByText('Acme S.A.')).toBeInTheDocument()
  })

  it('shows a confirmation message when the password change succeeds', async () => {
    installFetchMock({ changePasswordStatus: 204 })
    renderWithProviders(<SettingsPage />)
    const user = userEvent.setup()

    await screen.findByText('ana@acme.com')
    await user.type(screen.getByLabelText('Contraseña actual'), 'oldpassword123')
    await user.type(screen.getByLabelText('Contraseña nueva'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirmar contraseña nueva'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    await waitFor(() => {
      expect(screen.getByText('Contraseña actualizada correctamente.')).toBeInTheDocument()
    })
  })

  it('shows the backend error when the current password is incorrect', async () => {
    installFetchMock({
      changePasswordStatus: 400,
      changePasswordDetail: 'La contraseña actual no es correcta',
    })
    renderWithProviders(<SettingsPage />)
    const user = userEvent.setup()

    await screen.findByText('ana@acme.com')
    await user.type(screen.getByLabelText('Contraseña actual'), 'wrongpassword')
    await user.type(screen.getByLabelText('Contraseña nueva'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirmar contraseña nueva'), 'newpassword123')
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('La contraseña actual no es correcta')
    })
  })

  it('blocks submission before calling the backend when the new passwords do not match', async () => {
    const fetchMock = installFetchMock({})
    renderWithProviders(<SettingsPage />)
    const user = userEvent.setup()

    await screen.findByText('ana@acme.com')
    fetchMock.mockClear()

    await user.type(screen.getByLabelText('Contraseña actual'), 'oldpassword123')
    await user.type(screen.getByLabelText('Contraseña nueva'), 'newpassword123')
    await user.type(screen.getByLabelText('Confirmar contraseña nueva'), 'doesnotmatch123')
    await user.click(screen.getByRole('button', { name: 'Guardar contraseña' }))

    await waitFor(() => {
      expect(screen.getByText('Las contraseñas nuevas no coinciden.')).toBeInTheDocument()
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
