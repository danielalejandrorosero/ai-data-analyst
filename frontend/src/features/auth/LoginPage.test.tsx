import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/render'
import { LoginPage } from './LoginPage'
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

describe('LoginPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null })
    vi.restoreAllMocks()
  })

  it('renders email and password fields', () => {
    renderWithProviders(<LoginPage />)

    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña')).toBeInTheDocument()
  })

  it('shows an error message on invalid credentials (401)', async () => {
    mockAuthFetch(
      () =>
        new Response(JSON.stringify({ detail: 'Credenciales invalidas' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
    )

    renderWithProviders(<LoginPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'wrong-password')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Email o contraseña incorrectos.')
    })
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('stores the token on successful login', async () => {
    mockAuthFetch(
      () =>
        new Response(
          JSON.stringify({
            access_token: 'test-token',
            token_type: 'bearer',
            user: { id: '1', email: 'user@example.com', status: 'active', memberships: [] },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
    )

    renderWithProviders(<LoginPage />)
    const user = userEvent.setup()

    await user.type(screen.getByLabelText('Email'), 'user@example.com')
    await user.type(screen.getByLabelText('Contraseña'), 'correcthorsebattery')
    await user.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => {
      expect(useAuthStore.getState().token).toBe('test-token')
    })
  })
})
