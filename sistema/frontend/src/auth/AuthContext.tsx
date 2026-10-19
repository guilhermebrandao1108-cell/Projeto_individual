import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { post, request, setUnauthorizedHandler, tokenStore } from '../api/client'
import type { User } from '../api/types'
import { AuthContext } from './useAuth'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => tokenStore.get() !== null)
  const queryClient = useQueryClient()

  const logout = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!tokenStore.get()) return
    request<User>('/auth/me')
      .then(setUser)
      .catch(logout)
      .finally(() => setLoading(false))
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password })
    const { access_token } = await request<{ access_token: string }>('/auth/token', { method: 'POST', body: form })
    tokenStore.set(access_token)
    const me = await request<User>('/auth/me')
    setUser(me)
    return me
  }, [])

  const register = useCallback(
    async (name: string, email: string, password: string) => {
      await post<User>('/auth/register', { name, email, password })
      return login(email, password)
    },
    [login],
  )

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
