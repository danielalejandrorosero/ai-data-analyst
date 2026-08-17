import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/render'
import { ConnectionsPage } from './ConnectionsPage'
import { useAuthStore } from '../../lib/auth-store'
import type { ExternalConnection } from '../../api/datasets'
import type { Role } from '../../api/types'

function meUser(role: Role = 'ADMIN') {
  return {
    id: 'user-1',
    email: 'user@example.com',
    status: 'active',
    memberships: [{ organization_id: 'org-1', organization_name: 'Acme S.A.', role }],
  }
}

const CONNECTION: ExternalConnection = {
  id: 'conn-1',
  type: 'postgres',
  name: 'analytics_prod',
  host: 'db.acme.com',
  port: 5432,
  database_name: 'analytics',
  username: 'readonly_user',
  status: 'active',
  created_at: '2026-01-03T10:00:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function installFetchMock(opts: { role?: Role; connections?: ExternalConnection[] | 'error' }) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = typeof input === 'string' ? input : input.toString()

    if (url.includes('/auth/me')) {
      return Promise.resolve(jsonResponse(meUser(opts.role ?? 'ADMIN')))
    }
    if (url.includes('/datasets/connections')) {
      if (opts.connections === 'error') {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'Internal error' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      return Promise.resolve(jsonResponse(opts.connections ?? []))
    }
    throw new Error(`Unhandled fetch in test: ${url}`)
  })
}

describe('ConnectionsPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'test-token' })
    vi.restoreAllMocks()
  })

  it('shows the empty state and the registration form when there are no connections', async () => {
    installFetchMock({ connections: [] })
    renderWithProviders(<ConnectionsPage />)

    expect(await screen.findByText('Todavía no hay ninguna conexión registrada.')).toBeInTheDocument()
    expect(screen.getByText('Conectar PostgreSQL externo')).toBeInTheDocument()
  })

  it('shows the connection card and hides the form when a connection exists', async () => {
    installFetchMock({ connections: [CONNECTION] })
    renderWithProviders(<ConnectionsPage />)

    expect(await screen.findByText('analytics_prod')).toBeInTheDocument()
    expect(screen.getByText('db.acme.com')).toBeInTheDocument()
    expect(screen.getByText('5432')).toBeInTheDocument()
    expect(screen.getByText('analytics')).toBeInTheDocument()
    expect(screen.getByText('readonly_user')).toBeInTheDocument()

    expect(screen.queryByText('Conectar PostgreSQL externo')).not.toBeInTheDocument()
    expect(screen.queryByText('Todavía no hay ninguna conexión registrada.')).not.toBeInTheDocument()
  })

  it('never renders a password field or value for the registered connection', async () => {
    installFetchMock({ connections: [CONNECTION] })
    renderWithProviders(<ConnectionsPage />)

    await screen.findByText('analytics_prod')

    expect(screen.queryByText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/contraseña/i)).not.toBeInTheDocument()
  })

  it('hides the registration form for a VIEWER role even with no connections', async () => {
    installFetchMock({ role: 'VIEWER', connections: [] })
    renderWithProviders(<ConnectionsPage />)

    expect(await screen.findByText('Todavía no hay ninguna conexión registrada.')).toBeInTheDocument()
    expect(screen.queryByText('Conectar PostgreSQL externo')).not.toBeInTheDocument()
  })

  it('shows an error message when loading connections fails', async () => {
    installFetchMock({ connections: 'error' })
    renderWithProviders(<ConnectionsPage />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No se pudieron cargar las conexiones.')
  })
})
