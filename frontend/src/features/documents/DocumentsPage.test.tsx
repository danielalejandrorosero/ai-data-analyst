import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/render'
import { DocumentsPage } from './DocumentsPage'
import { useAuthStore } from '../../lib/auth-store'
import type { DocumentSearchResult, OrgDocument } from '../../api/documents'
import type { Role } from '../../api/types'

function meUser(role: Role = 'ANALYST') {
  return {
    id: 'user-1',
    email: 'user@example.com',
    status: 'active',
    memberships: [{ organization_id: 'org-1', organization_name: 'Acme S.A.', role }],
  }
}

const DOCUMENTS: OrgDocument[] = [
  {
    id: 'doc-1',
    organization_id: 'org-1',
    filename: 'manual.pdf',
    file_format: 'pdf',
    size_bytes: 204800,
    status: 'PROCESSING',
    error: null,
    chunk_count: 0,
    created_at: '2026-01-01T10:00:00Z',
  },
  {
    id: 'doc-2',
    organization_id: 'org-1',
    filename: 'definiciones.md',
    file_format: 'md',
    size_bytes: 10240,
    status: 'READY',
    error: null,
    chunk_count: 12,
    created_at: '2026-01-02T10:00:00Z',
  },
  {
    id: 'doc-3',
    organization_id: 'org-1',
    filename: 'reporte.docx',
    file_format: 'docx',
    size_bytes: 51200,
    status: 'FAILED',
    error: 'Formato de archivo corrupto',
    chunk_count: 0,
    created_at: '2026-01-03T10:00:00Z',
  },
]

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function installFetchMock(opts: {
  role?: Role
  documents?: OrgDocument[]
  searchResults?: DocumentSearchResult[]
}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET') as string

    if (url.includes('/auth/me')) {
      return Promise.resolve(jsonResponse(meUser(opts.role ?? 'ANALYST')))
    }
    if (url.includes('/documents/search')) {
      return Promise.resolve(jsonResponse(opts.searchResults ?? []))
    }
    if (method === 'DELETE') {
      return Promise.resolve(new Response(null, { status: 204 }))
    }
    if (url.includes('/documents')) {
      return Promise.resolve(jsonResponse(opts.documents ?? []))
    }
    throw new Error(`Unhandled fetch in test: ${method} ${url}`)
  })
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'test-token' })
    vi.restoreAllMocks()
  })

  it('shows the right status badge (and error message) for each document', async () => {
    installFetchMock({ documents: DOCUMENTS })
    renderWithProviders(<DocumentsPage />)

    await screen.findByText('manual.pdf')
    expect(screen.getByText('Indexando')).toBeInTheDocument()
    expect(screen.getByText('Listo')).toBeInTheDocument()
    expect(screen.getByText('Falló')).toBeInTheDocument()
    expect(screen.getByText('Formato de archivo corrupto')).toBeInTheDocument()
  })

  it('searches documents and shows the matching fragments', async () => {
    const results: DocumentSearchResult[] = [
      {
        document_id: 'doc-2',
        document_filename: 'definiciones.md',
        chunk_index: 0,
        content: 'Fragmento relevante sobre ventas trimestrales.',
        score: 0.91,
      },
    ]
    const fetchMock = installFetchMock({ documents: [DOCUMENTS[1]], searchResults: results })
    renderWithProviders(<DocumentsPage />)
    const user = userEvent.setup()

    const input = await screen.findByLabelText('Buscar en los documentos')
    await user.type(input, 'ventas trimestrales')
    await user.click(screen.getByRole('button', { name: 'Buscar' }))

    expect(await screen.findByText('Fragmento relevante sobre ventas trimestrales.')).toBeInTheDocument()

    const searchCall = fetchMock.mock.calls.find(([requestUrl]) => String(requestUrl).includes('/documents/search'))
    expect(searchCall).toBeDefined()
    const searchUrl = new URL(String(searchCall![0]))
    expect(searchUrl.searchParams.get('q')).toBe('ventas trimestrales')
  })

  it('hides upload and delete for a VIEWER role', async () => {
    installFetchMock({ role: 'VIEWER', documents: DOCUMENTS })
    renderWithProviders(<DocumentsPage />)

    await screen.findByText('manual.pdf')
    expect(screen.queryByText(/Arrastrá un documento/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Eliminar/ })).not.toBeInTheDocument()
  })

  it('shows upload but hides delete for an ANALYST role', async () => {
    installFetchMock({ role: 'ANALYST', documents: DOCUMENTS })
    renderWithProviders(<DocumentsPage />)

    await screen.findByText('manual.pdf')
    expect(screen.getByText(/Arrastrá un documento/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Eliminar/ })).not.toBeInTheDocument()
  })

  it('shows both upload and delete for an OWNER/ADMIN role', async () => {
    installFetchMock({ role: 'OWNER', documents: DOCUMENTS })
    renderWithProviders(<DocumentsPage />)

    await screen.findByText('manual.pdf')
    expect(screen.getByText(/Arrastrá un documento/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Eliminar/ }).length).toBeGreaterThan(0)
  })

  it('deletes a document when the delete button is clicked', async () => {
    const fetchMock = installFetchMock({ role: 'OWNER', documents: [DOCUMENTS[1]] })
    renderWithProviders(<DocumentsPage />)
    const user = userEvent.setup()

    const deleteButton = await screen.findByRole('button', { name: 'Eliminar definiciones.md' })
    await user.click(deleteButton)

    await vi.waitFor(() => {
      const deleteCall = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'DELETE')
      expect(deleteCall).toBeDefined()
    })

    const deleteCall = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'DELETE')!
    expect(String(deleteCall[0])).toContain('/documents/doc-2')
  })
})
