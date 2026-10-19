import { createContext, useContext } from 'react'
import type { User } from '../api/types'

export interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (name: string, email: string, password: string) => Promise<User>
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}

export const homeFor = (user: User) => (user.role === 'cliente' ? '/chamados' : user.role === 'gestor' ? '/painel' : '/fila')
