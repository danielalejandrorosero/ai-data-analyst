// Tipos alineados a mano con backend/app/domain/agent/schemas.py y
// backend/app/db/models/analysis.py (AnalysisStatus).
import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, openEventStream } from './client'

export type AnalysisStatus =
  | 'QUEUED'
  | 'PLANNING'
  | 'TOOL_RUNNING'
  | 'ANALYZING'
  | 'GENERATING_RESPONSE'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'TIMED_OUT'

export const TERMINAL_STATUSES: AnalysisStatus[] = ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT']

export function isTerminalStatus(status: AnalysisStatus): boolean {
  return TERMINAL_STATUSES.includes(status)
}

export interface ToolCall {
  tool: string
  status: 'SUCCESS' | 'ERROR'
  duration_ms: number
  output_summary: Record<string, unknown> | null
  error_message: string | null
}

export interface QueryResult {
  sql: string
  columns: string[]
  row_count: number
  truncated: boolean
  rows: unknown[][]
  evidence_truncated: boolean
}

export interface Analysis {
  id: string
  dataset_id: string
  question: string
  status: AnalysisStatus
  answer: string | null
  result: QueryResult[] | null
  error: string | null
  created_at: string
  tool_calls: ToolCall[]
}

export interface AnalysisListItem {
  id: string
  dataset_id: string
  question: string
  status: AnalysisStatus
  created_at: string
}

export interface AnalysisArtifact {
  id: string
  type: string
  spec: {
    chart_type: 'bar' | 'line' | 'pie' | 'scatter'
    title: string
    x_field: string
    y_field: string
    data: Record<string, unknown>[]
    data_truncated: boolean
  }
  source_sql: string
  created_at: string
}

export function useAnalyses(organizationId: string | undefined, token: string | null) {
  return useQuery({
    queryKey: ['analyses', organizationId],
    queryFn: () => apiFetch<AnalysisListItem[]>('/analyses', { token, query: { organization_id: organizationId } }),
    enabled: organizationId !== undefined,
  })
}

export function useCreateAnalysis(organizationId: string | undefined, token: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ datasetId, question }: { datasetId: string; question: string }) =>
      apiFetch<Analysis>('/analyses', {
        method: 'POST',
        body: { dataset_id: datasetId, question },
        token,
      }),
    onSuccess: (analysis) => {
      queryClient.invalidateQueries({ queryKey: ['analyses', organizationId] })
      queryClient.setQueryData(['analyses', 'detail', analysis.id], analysis)
    },
  })
}

// Postgres via GET /analyses/{id} es la fuente de verdad (mismo criterio que
// el backend, backend/app/api/analyses.py) - el refetchInterval es el
// fallback explicito que pide .claude/rules/frontend.md cuando no hay stream
// SSE activo; useAnalysisEventStream invalida esta query apenas llega un
// evento para no depender solo del polling mientras el analisis corre.
export function useAnalysis(analysisId: string | null, token: string | null) {
  return useQuery({
    queryKey: ['analyses', 'detail', analysisId],
    queryFn: () => apiFetch<Analysis>(`/analyses/${analysisId}`, { token }),
    enabled: analysisId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || !isTerminalStatus(status)) return 4000
      return false
    },
  })
}

export function useCancelAnalysis(token: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (analysisId: string) =>
      apiFetch<{ id: string; status: string }>(`/analyses/${analysisId}/cancel`, {
        method: 'POST',
        token,
      }),
    onSuccess: (_data, analysisId) => {
      queryClient.invalidateQueries({ queryKey: ['analyses', 'detail', analysisId] })
    },
  })
}

export function useAnalysisArtifacts(analysisId: string | null, token: string | null) {
  return useQuery({
    queryKey: ['analyses', 'detail', analysisId, 'artifacts'],
    queryFn: () => apiFetch<AnalysisArtifact[]>(`/analyses/${analysisId}/artifacts`, { token }),
    enabled: analysisId !== null,
  })
}

// RF-020/RF-025: mientras el analisis no llega a un estado terminal, cada
// mensaje del stream SSE fuerza un refetch inmediato de GET /analyses/{id}
// (y de sus artifacts) en vez de esperar al proximo tick del polling de
// fallback - el contenido del evento no se usa directamente porque Postgres
// ya es la fuente de verdad completa (incluye tool_calls con su propio
// input/output, que el evento SSE no trae).
export function useAnalysisEventStream(
  analysisId: string | null,
  token: string | null,
  active: boolean,
) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!analysisId || !active) return

    const controller = new AbortController()

    async function consume() {
      const reader = await openEventStream(`/analyses/${analysisId}/events`, token, controller.signal)
      if (!reader) return

      const decoder = new TextDecoder()
      let buffer = ''
      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const messages = buffer.split('\n\n')
          buffer = messages.pop() ?? ''
          for (const message of messages) {
            if (!message.trim()) continue
            queryClient.invalidateQueries({ queryKey: ['analyses', 'detail', analysisId] })
            queryClient.invalidateQueries({ queryKey: ['analyses', 'detail', analysisId, 'artifacts'] })
          }
        }
      } catch {
        // Conexion cortada (navegacion, red) - el polling de useAnalysis sigue como fallback.
      }
    }

    consume()
    return () => controller.abort()
  }, [analysisId, token, active, queryClient])
}

export function useExportAnalysis() {
  return useMutation({
    mutationFn: async ({
      analysisId,
      token,
      format,
      queryIndex,
    }: {
      analysisId: string
      token: string | null
      format: 'csv' | 'json'
      queryIndex: number
    }) => {
      const params = new URLSearchParams({ format, query_index: String(queryIndex) })
      const base = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api') as string
      const response = await fetch(`${base}/analyses/${analysisId}/export?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!response.ok) throw new Error('No se pudo exportar el resultado')

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `analysis-${analysisId}.${format}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    },
  })
}
