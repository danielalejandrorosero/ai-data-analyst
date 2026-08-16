// Cliente HTTP fino, sin dependencias - toda llamada a la API pasa por acá
// (nunca fetch/axios sueltos dentro de componentes, .claude/rules/frontend.md).
// Los hooks de TanStack Query en src/api/*.ts son los únicos consumidores.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

// El router de /health vive en la raiz del servidor, sin el prefijo /api
// (backend/app/main.py) - no es parte del contrato versionable de la API.
export const HEALTH_BASE_URL = API_BASE_URL.replace(/\/api\/?$/, '')

export class ApiError extends Error {
  status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  formData?: FormData
  token?: string | null
  query?: Record<string, string | number | undefined>
  baseUrl?: string
}

function buildUrl(path: string, query?: ApiFetchOptions['query'], baseUrl: string = API_BASE_URL): string {
  const url = new URL(`${baseUrl}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.set(key, String(value))
  }
  return url.toString()
}

interface ValidationErrorItem {
  loc?: unknown[]
  msg?: string
}

function isValidationErrorList(detail: unknown): detail is ValidationErrorItem[] {
  return (
    Array.isArray(detail) &&
    detail.length > 0 &&
    detail.every((item) => typeof item === 'object' && item !== null && 'msg' in item)
  )
}

// FastAPI/Pydantic devuelven los 422 como una lista de errores de validacion,
// no como string - sin esto se le mostraba al usuario el JSON crudo.
function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (isValidationErrorList(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item.loc) ? item.loc.at(-1) : undefined
        return field ? `${field}: ${item.msg}` : (item.msg ?? '')
      })
      .join('; ')
  }
  return JSON.stringify(detail)
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (options.token) headers.Authorization = `Bearer ${options.token}`

  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }

  const response = await fetch(buildUrl(path, options.query, options.baseUrl), {
    method: options.method ?? 'GET',
    headers,
    body,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const data = (await response.json()) as { detail?: unknown }
      if (data.detail !== undefined) {
        detail = formatDetail(data.detail)
      }
    } catch {
      // El body no era JSON - se mantiene el statusText.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
