import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/render'
import { DatasetsPage } from './DatasetsPage'
import { useAuthStore } from '../../lib/auth-store'
import type { Dataset, DatasetSchema } from '../../api/datasets'
import type { Role } from '../../api/types'

function meUser(role: Role = 'ANALYST') {
  return {
    id: 'user-1',
    email: 'user@example.com',
    status: 'active',
    memberships: [{ organization_id: 'org-1', organization_name: 'Acme S.A.', role }],
  }
}

const DATASETS: Dataset[] = [
  {
    id: 'ds-1',
    organization_id: 'org-1',
    source_id: 'src-1',
    source_type: 'upload',
    source_extension: 'csv',
    name: 'ventas.csv',
    row_count: 1200,
    column_count: 6,
    created_at: '2026-01-01T10:00:00Z',
  },
  {
    id: 'ds-2',
    organization_id: 'org-1',
    source_id: 'src-2',
    source_type: 'upload',
    source_extension: 'xlsx',
    name: 'inventario.xlsx',
    row_count: 340,
    column_count: 9,
    created_at: '2026-01-02T10:00:00Z',
  },
  {
    id: 'ds-3',
    organization_id: 'org-1',
    source_id: 'src-3',
    source_type: 'postgres',
    source_extension: null,
    name: 'analytics_prod',
    row_count: 500000,
    column_count: 14,
    created_at: '2026-01-03T10:00:00Z',
  },
]

const SCHEMA: DatasetSchema = {
  id: 'ds-1',
  name: 'ventas.csv',
  row_count: 1200,
  columns: [
    { name: 'id', type: 'integer' },
    { name: 'monto', type: 'numeric' },
  ],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function installFetchMock(opts: { role?: Role; datasets?: Dataset[] | 'error'; schema?: DatasetSchema }) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
    const url = typeof input === 'string' ? input : input.toString()

    if (url.includes('/auth/me')) {
      return Promise.resolve(jsonResponse(meUser(opts.role ?? 'ANALYST')))
    }
    if (url.includes('/schema')) {
      return Promise.resolve(jsonResponse(opts.schema ?? SCHEMA))
    }
    if (url.includes('/datasets')) {
      if (opts.datasets === 'error') {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: 'Internal error' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      return Promise.resolve(jsonResponse(opts.datasets ?? []))
    }
    throw new Error(`Unhandled fetch in test: ${url}`)
  })
}

describe('DatasetsPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'test-token' })
    vi.restoreAllMocks()
  })

  it('loads and displays datasets with their format chip', async () => {
    installFetchMock({ datasets: DATASETS })
    renderWithProviders(<DatasetsPage />)

    expect(await screen.findByText('ventas.csv')).toBeInTheDocument()
    expect(screen.getByText('inventario.xlsx')).toBeInTheDocument()
    expect(screen.getByText('analytics_prod')).toBeInTheDocument()

    expect(screen.getByText('CSV')).toBeInTheDocument()
    expect(screen.getByText('XLSX')).toBeInTheDocument()
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument()
  })

  it('shows an empty state message when there are no datasets', async () => {
    installFetchMock({ datasets: [] })
    renderWithProviders(<DatasetsPage />)

    expect(await screen.findByText('Todavía no hay datasets importados.')).toBeInTheDocument()
  })

  it('shows an error message when loading datasets fails', async () => {
    installFetchMock({ datasets: 'error' })
    renderWithProviders(<DatasetsPage />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('No se pudieron cargar los datasets.')
  })

  it('hides upload and connect actions for a VIEWER role', async () => {
    installFetchMock({ role: 'VIEWER', datasets: DATASETS })
    renderWithProviders(<DatasetsPage />)

    await screen.findByText('ventas.csv')

    expect(screen.queryByText(/Arrastrá un CSV o Excel/)).not.toBeInTheDocument()
    expect(screen.queryByText('Conectar PostgreSQL externo')).not.toBeInTheDocument()
  })

  it('opens the schema modal with columns when a dataset card is clicked', async () => {
    installFetchMock({ datasets: DATASETS, schema: SCHEMA })
    renderWithProviders(<DatasetsPage />)
    const user = userEvent.setup()

    const card = await screen.findByText('ventas.csv')
    await user.click(card)

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('id')).toBeInTheDocument()
    expect(within(dialog).getByText('monto')).toBeInTheDocument()
    expect(within(dialog).getByText('integer')).toBeInTheDocument()
    expect(within(dialog).getByText('numeric')).toBeInTheDocument()
  })
})
