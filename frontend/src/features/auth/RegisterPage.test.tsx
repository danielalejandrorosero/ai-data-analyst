import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/render'
import { RegisterPage } from './RegisterPage'
import { useAuthStore } from '../../lib/auth-store'

function healthResponse() {
  return new Response(JSON.stringify({ status: 'ok', checks: { database: 'ok', redis: 'ok' } }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

function mockAuthFetch(authResponseFactory: () => Response) {
  vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = typeof input === 'string' ? input : input.toString()
    return Promise.resolve(url.includes('/health/ready') ? healthResponse() : authResponseFactory())
  })
}

describe('RegisterPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null })
    vi.restoreAllMocks()
  })

  it('renders organization, email and password fields', () => {
    renderWithProviders(<RegisterPage />)

    expect(screen.getByLabelText('Nombre de la organización')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña')).toBeInTheDocument()
  })

  it('shows an error message when the email is already registered (409)', async () => {
    mockAuthFetch(
      () =>
        new Response(JSON.stringify({ detail: 'organization already exists' }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        }),
    )

    renderWithProviders(<RegisterPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Nombre de la organización'), 'Acme S.A.')
    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'correcthorsebattery')
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Ese email ya está registrado.')
    })
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('stores the token and registers the organization on success', async () => {
    mockAuthFetch(
      () =>
        new Response(
          JSON.stringify({
            access_token: 'test-token',
            token_type: 'bearer',
            user: {
              id: '1',
              email: 'user@example.com',
              status: 'active',
              memberships: [{ organization_name: 'Acme S.A.', role: 'OWNER' }],
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    )

    renderWithProviders(<RegisterPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Nombre de la organización'), 'Acme S.A.')
    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'correcthorsebattery')
    await user.click(screen.getByRole('button', { name: 'Crear cuenta' }))

    await waitFor(() => {
      expect(useAuthStore.getState().token).toBe('test-token')
    })
  })
})
