import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/render'
import { AnalysisPage } from './AnalysisPage'
import { useAuthStore } from '../../lib/auth-store'
import type { Analysis, AnalysisListItem } from '../../api/analyses'
import type { Dataset } from '../../api/datasets'
import type { Role } from '../../api/types'

function meUser(role: Role = 'ANALYST') {
  return {
    id: 'user-1',
    email: 'user@example.com',
    status: 'active',
    memberships: [{ organization_id: 'org-1', organization_name: 'Acme S.A.', role }],
  }
}

const DATASET: Dataset = {
  id: 'ds-1',
  organization_id: 'org-1',
  source_id: 'src-1',
  source_type: 'upload',
  source_extension: 'csv',
  name: 'ventas.csv',
  row_count: 1200,
  column_count: 6,
  created_at: '2026-01-01T10:00:00Z',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

// EventSource nativo no funciona sobre el fetch mockeado de jsdom - en vez
// de mockear el hook useAnalysisEventStream directamente, se deja que
// abra la conexion real (via fetch, src/api/client.ts openEventStream) y se
// le responde con un body vacio: la respuesta "ok" sin body hace que
// openEventStream devuelva null y el hook corte ahi mismo, sin flakiness ni
// necesidad de streaming real en el entorno de test.
function eventsResponse(): Response {
  return new Response(null, { status: 200 })
}

function installFetchMock(opts: {
  role?: Role
  datasets?: Dataset[]
  analyses?: AnalysisListItem[]
  analysisDetails?: Record<string, Analysis>
  onCreateAnalysis?: (body: { dataset_id: string; question: string }) => Analysis
}) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = typeof input === 'string' ? input : input.toString()
    const method = (init?.method ?? 'GET') as string

    if (url.includes('/events')) {
      return Promise.resolve(eventsResponse())
    }
    if (url.includes('/auth/me')) {
      return Promise.resolve(jsonResponse(meUser(opts.role ?? 'ANALYST')))
    }
    if (url.includes('/artifacts')) {
      return Promise.resolve(jsonResponse([]))
    }
    if (method === 'POST' && url.endsWith('/analyses')) {
      const body = JSON.parse(String(init?.body)) as { dataset_id: string; question: string }
      const created =
        opts.onCreateAnalysis?.(body) ??
        ({
          id: 'an-new',
          dataset_id: body.dataset_id,
          question: body.question,
          status: 'QUEUED',
          answer: null,
          result: null,
          error: null,
          created_at: '2026-01-04T10:00:00Z',
          tool_calls: [],
        } satisfies Analysis)
      return Promise.resolve(jsonResponse(created))
    }
    const detailMatch = url.match(/\/analyses\/([\w-]+)(?:\?|$)/)
    if (detailMatch && opts.analysisDetails?.[detailMatch[1]]) {
      return Promise.resolve(jsonResponse(opts.analysisDetails[detailMatch[1]]))
    }
    if (url.includes('/analyses')) {
      return Promise.resolve(jsonResponse(opts.analyses ?? []))
    }
    if (url.includes('/datasets')) {
      return Promise.resolve(jsonResponse(opts.datasets ?? [DATASET]))
    }
    throw new Error(`Unhandled fetch in test: ${method} ${url}`)
  })
}

describe('AnalysisPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'test-token' })
    vi.restoreAllMocks()
  })

  it('shows the empty-thread message when there are datasets but no analyses yet', async () => {
    installFetchMock({ analyses: [] })
    renderWithProviders(<AnalysisPage />)

    expect(await screen.findByText('Hacé tu primera pregunta sobre este dataset.')).toBeInTheDocument()
  })

  it('renders an existing thread in chronological order (oldest on top, newest at the bottom)', async () => {
    // La API lista mas recientes primero.
    const analysesList: AnalysisListItem[] = [
      { id: 'an-2', dataset_id: 'ds-1', question: '¿Cuál fue la segunda pregunta?', status: 'COMPLETED', created_at: '2026-01-02T10:00:00Z' },
      { id: 'an-1', dataset_id: 'ds-1', question: '¿Cuál fue la primera pregunta?', status: 'COMPLETED', created_at: '2026-01-01T10:00:00Z' },
    ]
    const detail = (id: string, question: string): Analysis => ({
      id,
      dataset_id: 'ds-1',
      question,
      status: 'COMPLETED',
      answer: 'Análisis completado exitosamente.',
      result: [],
      error: null,
      created_at: '2026-01-01T10:00:00Z',
      tool_calls: [],
    })

    installFetchMock({
      analyses: analysesList,
      analysisDetails: {
        'an-1': detail('an-1', '¿Cuál fue la primera pregunta?'),
        'an-2': detail('an-2', '¿Cuál fue la segunda pregunta?'),
      },
    })
    renderWithProviders(<AnalysisPage />)

    await screen.findByText('Análisis completado exitosamente.')
    // DatasetChatList tambien muestra la ultima pregunta de cada chat en el
    // sidebar (un <span>) - se filtra por el <p> del globo de chat para no
    // confundir ambas apariciones.
    const bubbles = (await screen.findAllByText(/¿Cuál fue la (primera|segunda) pregunta\?/)).filter(
      (el) => el.tagName === 'P',
    )
    expect(bubbles).toHaveLength(2)
    expect(bubbles[0]).toHaveTextContent('primera')
    expect(bubbles[1]).toHaveTextContent('segunda')
  })

  it('hides the question input and shows a permission message for a VIEWER role', async () => {
    installFetchMock({ role: 'VIEWER', analyses: [] })
    renderWithProviders(<AnalysisPage />)

    expect(await screen.findByText('Tu rol (VIEWER) no tiene permiso para ejecutar análisis.')).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/Preguntá algo sobre tus datos/)).not.toBeInTheDocument()
  })

  it('submits a new question with the correct dataset_id and text', async () => {
    const fetchMock = installFetchMock({ role: 'ANALYST', analyses: [] })
    renderWithProviders(<AnalysisPage />)
    const user = userEvent.setup()

    const textbox = await screen.findByPlaceholderText(/Preguntá algo sobre tus datos/)
    await user.type(textbox, '¿Cuál fue el monto total de ventas?')
    await user.click(screen.getByRole('button', { name: 'Enviar pregunta' }))

    await vi.waitFor(() => {
      const postCall = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'POST')
      expect(postCall).toBeDefined()
    })

    const postCall = fetchMock.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === 'POST')!
    const [url, init] = postCall
    expect(String(url)).toContain('/analyses')
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      dataset_id: 'ds-1',
      question: '¿Cuál fue el monto total de ventas?',
    })
  })
})
