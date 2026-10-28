import { createContext, use, useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useSWRConfig } from 'swr'
import {
  api,
  clearSession,
  getRefreshToken,
  hasStoredSession,
  onSessionExpired,
  refreshAccessToken,
  setSession,
} from './api'
import type { Profile } from './types'

type Status = 'loading' | 'anonymous' | 'authenticated'

interface AuthContextValue {
  status: Status
  user: Profile | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setUser: (user: Profile) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { mutate } = useSWRConfig()
  const [user, setUser] = useState<Profile | null>(null)
  // A stored refresh token means we may still be logged in: resolve it on mount.
  const [status, setStatus] = useState<Status>(() =>
    hasStoredSession() ? 'loading' : 'anonymous',
  )

  const reset = useCallback(() => {
    clearSession()
    setUser(null)
    setStatus('anonymous')
    // Drop every cached response of the previous user.
    void mutate(() => true, undefined, { revalidate: false })
  }, [mutate])

  useEffect(() => {
    if (status !== 'loading') return
    let cancelled = false
    ;(async () => {
      const token = await refreshAccessToken()
      if (!token) {
        if (!cancelled) reset()
        return
      }
      try {
        const profile = await api<Profile>('/api/auth/me/')
        if (!cancelled) {
          setUser(profile)
          setStatus('authenticated')
        }
      } catch {
        if (!cancelled) reset()
      }
    })()
    return () => {
      cancelled = true
    }
  }, [status, reset])

  useEffect(() => onSessionExpired(reset), [reset])

  const login = useCallback(async (email: string, password: string) => {
    const data = await api<{ access: string; refresh: string; user: Profile }>(
      '/api/auth/login/',
      { method: 'POST', body: { email, password } },
    )
    setSession(data.access, data.refresh)
    setUser(data.user)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    const refresh = getRefreshToken()
    if (refresh) {
      await api('/api/auth/logout/', { method: 'POST', body: { refresh } }).catch(() => {})
    }
    reset()
  }, [reset])

  const value = useMemo(
    () => ({ status, user, login, logout, setUser }),
    [status, user, login, logout],
  )
  return <AuthContext value={value}>{children}</AuthContext>
}

export function useAuth() {
  const context = use(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
