// Tipos alineados a mano con backend/app/domain/documents/schemas.py.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'

export type DocumentStatus = 'PROCESSING' | 'READY' | 'FAILED'

export interface OrgDocument {
  id: string
  organization_id: string
  filename: string
  file_format: 'pdf' | 'txt' | 'md' | 'docx'
  size_bytes: number
  status: DocumentStatus
  error: string | null
  chunk_count: number
  created_at: string
}

export interface DocumentSearchResult {
  document_id: string
  document_filename: string
  chunk_index: number
  content: string
  score: number
}

// Mientras haya documentos en PROCESSING (la ingesta corre en el worker,
// RF-061) se refresca solo - al quedar todos terminales, se corta.
export function useDocuments(organizationId: string | undefined, token: string | null) {
  return useQuery({
    queryKey: ['documents', organizationId],
    queryFn: () => apiFetch<OrgDocument[]>('/documents', { token, query: { organization_id: organizationId } }),
    enabled: organizationId !== undefined,
    refetchInterval: (query) => {
      const documents = query.state.data
      if (documents?.some((d) => d.status === 'PROCESSING')) return 3000
      return false
    },
  })
}

export function useUploadDocument(organizationId: string | undefined, token: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('organization_id', organizationId ?? '')
      formData.append('file', file)
      return apiFetch<OrgDocument>('/documents', { method: 'POST', formData, token })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', organizationId] })
    },
  })
}

export function useDeleteDocument(organizationId: string | undefined, token: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (documentId: string) =>
      apiFetch<void>(`/documents/${documentId}`, { method: 'DELETE', token }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', organizationId] })
    },
  })
}

export function useSearchDocuments(
  organizationId: string | undefined,
  token: string | null,
  query: string,
) {
  return useQuery({
    queryKey: ['documents', organizationId, 'search', query],
    queryFn: () =>
      apiFetch<DocumentSearchResult[]>('/documents/search', {
        token,
        query: { organization_id: organizationId, q: query },
      }),
    enabled: organizationId !== undefined && query.trim().length > 0,
  })
}
