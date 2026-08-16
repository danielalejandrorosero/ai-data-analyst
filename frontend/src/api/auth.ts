import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from './client'
import type { TokenResponse, User } from './types'
import { useAuthStore } from '../lib/auth-store'

interface RegisterInput {
  email: string
  password: string
  organization_name: string
}

interface LoginInput {
  email: string
  password: string
}

export function useRegister() {
  const setToken = useAuthStore((s) => s.setToken)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: RegisterInput) =>
      apiFetch<TokenResponse>('/auth/register', { method: 'POST', body: input }),
    onSuccess: (data) => {
      setToken(data.access_token)
      queryClient.setQueryData(['me'], data.user)
    },
  })
}

export function useLogin() {
  const setToken = useAuthStore((s) => s.setToken)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: LoginInput) =>
      apiFetch<TokenResponse>('/auth/login', { method: 'POST', body: input }),
    onSuccess: (data) => {
      setToken(data.access_token)
      queryClient.setQueryData(['me'], data.user)
    },
  })
}

export function useMe() {
  const token = useAuthStore((s) => s.token)

  return useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch<User>('/auth/me', { token }),
    enabled: token !== null,
    retry: false,
  })
}

export function useLogout() {
  const clearToken = useAuthStore((s) => s.clearToken)
  const queryClient = useQueryClient()

  return () => {
    clearToken()
    queryClient.removeQueries({ queryKey: ['me'] })
  }
}
