const BASE = '/api'
const TOKEN_KEY = 'chamados.token'

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set: (token: string | null) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token)
      else localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* storage unavailable: the session lasts until reload */
    }
  },
}

// FastAPI returns {detail: string} for our errors and {detail: [{msg, loc}]} for validation errors.
function errorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: { msg?: string }) => d.msg?.replace(/^Value error, /, '') ?? '').join(' · ')
  }
  return fallback
}

let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof URLSearchParams)) headers.set('Content-Type', 'application/json')

  const response = await fetch(BASE + path, { ...init, headers })
  if (response.status === 401 && token) onUnauthorized()
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, errorMessage(body, `Erro ${response.status}`))
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

/** Authenticated file download (an <a href> could not send the bearer token). */
export async function download(path: string, fallbackName: string): Promise<void> {
  const token = tokenStore.get()
  const response = await fetch(BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, errorMessage(body, `Erro ${response.status}`))
  }
  const name = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') ?? '')?.[1] ?? fallbackName
  const url = URL.createObjectURL(await response.blob())
  const link = Object.assign(document.createElement('a'), { href: url, download: name })
  link.click()
  URL.revokeObjectURL(url)
}

export const post = <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const patch = <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) })

export function query(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '' && value !== false) search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}
