// Tipos alineados a mano con backend/app/domain/datasets/schemas.py.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'

export interface ColumnSchema {
  name: string
  type: string
}

export type DatasetSourceType = 'upload' | 'postgres'

export interface Dataset {
  id: string
  organization_id: string
  source_id: string
  source_type: DatasetSourceType
  source_extension: 'csv' | 'xlsx' | null
  name: string
  row_count: number
  column_count: number
  created_at: string
}

export interface DatasetSchema {
  id: string
  name: string
  row_count: number
  columns: ColumnSchema[]
}

export interface ExternalConnectionInput {
  type: 'postgres'
  name: string
  host: string
  port: number
  database_name: string
  username: string
  password: string
}

export interface ExternalConnection {
  id: string
  type: string
  name: string
  host: string
  port: number
  database_name: string
  username: string
  status: string
  created_at: string
}

export function useDatasets(organizationId: string | undefined, token: string | null) {
  return useQuery({
    queryKey: ['datasets', organizationId],
    queryFn: () => apiFetch<Dataset[]>('/datasets', { token, query: { organization_id: organizationId } }),
    enabled: organizationId !== undefined,
  })
}

export function useDatasetSchema(datasetId: string | null, token: string | null) {
  return useQuery({
    queryKey: ['datasets', datasetId, 'schema'],
    queryFn: () => apiFetch<DatasetSchema>(`/datasets/${datasetId}/schema`, { token }),
    enabled: datasetId !== null,
  })
}

export function useImportDataset(organizationId: string | undefined, token: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) => {
      const formData = new FormData()
      formData.append('organization_id', organizationId ?? '')
      formData.append('file', file)
      if (name) formData.append('name', name)
      return apiFetch<DatasetSchema>('/datasets/import', { method: 'POST', formData, token })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['datasets', organizationId] })
    },
  })
}

export function useRegisterConnection(organizationId: string | undefined, token: string | null) {
  return useMutation({
    mutationFn: (input: ExternalConnectionInput) =>
      apiFetch<ExternalConnection>('/datasets/connections', {
        method: 'POST',
        body: input,
        token,
        query: { organization_id: organizationId },
      }),
  })
}
