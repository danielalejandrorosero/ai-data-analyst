import { useQuery } from '@tanstack/react-query'
import { apiFetch, HEALTH_BASE_URL } from './client'

interface ReadinessResponse {
  status: 'ok' | 'degraded'
  checks: Record<string, string>
}

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health', 'ready'],
    queryFn: () => apiFetch<ReadinessResponse>('/health/ready', { baseUrl: HEALTH_BASE_URL }),
    refetchInterval: 20_000,
    retry: false,
  })
}
