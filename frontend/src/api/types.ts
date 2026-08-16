// Tipos alineados a mano con los schemas Pydantic del backend (frontend/CLAUDE.md).
// Fuente de verdad: backend/app/domain/auth/schemas.py

export type Role = 'OWNER' | 'ADMIN' | 'ANALYST' | 'VIEWER'

export interface Membership {
  organization_id: string
  organization_name: string
  role: Role
}

export interface User {
  id: string
  email: string
  status: string
  memberships: Membership[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}
