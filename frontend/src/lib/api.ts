/**
 * Fetch wrapper for the Django API.
 *
 * The access token lives in memory only; the refresh token is kept in localStorage
 * so a reload keeps the session. A 401 triggers one shared refresh, then the request
 * is replayed once.
 */

const SESSION_KEY = 'coldchain.session.v1'

let accessToken: string | null = null
let refreshing: Promise<string | null> | null = null
const expiryListeners = new Set<() => void>()

export class ApiError extends Error {
  status: number
  data: unknown

  constructor(status: number, data: unknown) {
    super(errorMessage(data) ?? `Erreur ${status}`)
    this.status = status
    this.data = data
  }
}

function readRefreshToken(): string | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as { refresh?: string }).refresh ?? null : null
  } catch {
    return null
  }
}

function writeRefreshToken(refresh: string | null) {
  try {
    if (refresh) localStorage.setItem(SESSION_KEY, JSON.stringify({ refresh }))
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // Private mode / blocked storage: the session simply won't survive a reload.
  }
}

export function setSession(access: string, refresh: string) {
  accessToken = access
  writeRefreshToken(refresh)
}

export function clearSession() {
  accessToken = null
  writeRefreshToken(null)
}

export function hasStoredSession() {
  return readRefreshToken() !== null
}

export function getRefreshToken() {
  return readRefreshToken()
}

/** Called when the session can no longer be renewed. */
export function onSessionExpired(listener: () => void) {
  expiryListeners.add(listener)
  return () => {
    expiryListeners.delete(listener)
  }
}

export function refreshAccessToken(): Promise<string | null> {
  const refresh = readRefreshToken()
  if (!refresh) return Promise.resolve(null)
  refreshing ??= (async () => {
    try {
      const response = await fetch('/api/auth/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      })
      if (!response.ok) {
        clearSession()
        return null
      }
      const data = (await response.json()) as { access: string; refresh?: string }
      accessToken = data.access
      if (data.refresh) writeRefreshToken(data.refresh)
      return data.access
    } catch {
      return null
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

type Query = Record<string, string | number | boolean | null | undefined>

export function buildUrl(path: string, query?: Query) {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${path}${path.includes('?') ? '&' : '?'}${qs}` : path
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Query
}

async function send(url: string, options: RequestOptions, token: string | null) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  return fetch(url, {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })
}

async function fetchWithAuth(path: string, options: RequestOptions = {}) {
  const url = buildUrl(path, options.query)
  let response = await send(url, options, accessToken)
  if (response.status === 401 && readRefreshToken()) {
    const token = await refreshAccessToken()
    if (token) {
      response = await send(url, options, token)
    } else {
      expiryListeners.forEach((listener) => listener())
    }
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new ApiError(response.status, data)
  }
  return response
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetchWithAuth(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Download a file (CSV export) with the auth header, then save it. */
export async function download(path: string, query: Query, fallbackName: string) {
  const response = await fetchWithAuth(path, { query })
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  URL.revokeObjectURL(url)
}

/** SWR fetcher: the key is the API path. */
export const fetcher = <T,>(path: string) => api<T>(path)

/** Human-readable message from a DRF error payload. */
export function errorMessage(data: unknown): string | null {
  if (!data) return null
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data.map(errorMessage).filter(Boolean).join(' ')
  if (typeof data === 'object') {
    const record = data as Record<string, unknown>
    if (record.detail) return errorMessage(record.detail)
    if (record.non_field_errors) return errorMessage(record.non_field_errors)
    const first = Object.values(record)[0]
    return errorMessage(first)
  }
  return null
}

/** Field errors of a DRF 400 response, keyed by field name. */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || error.status !== 400) return {}
  const data = error.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) return {}
  const result: Record<string, string> = {}
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    result[key] = errorMessage(value) ?? ''
  }
  return result
}

export function describeError(error: unknown) {
  if (error instanceof ApiError) return error.message
  return 'Le serveur est injoignable. Vérifiez votre connexion.'
}
