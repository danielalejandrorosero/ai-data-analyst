import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Solo el token de sesion vive aca (estado que TanStack Query no puede
// modelar). El usuario/organizaciones se obtienen via useMe() (TanStack
// Query, src/api/auth.ts) - no se duplica en este store (frontend/CLAUDE.md,
// .claude/rules/frontend.md: "no duplicar en Zustand estado que ya vive en
// TanStack Query").
interface AuthState {
  token: string | null
  setToken: (token: string) => void
  clearToken: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      setToken: (token) => set({ token }),
      clearToken: () => set({ token: null }),
    }),
    { name: 'ai-data-analyst-auth' },
  ),
)
