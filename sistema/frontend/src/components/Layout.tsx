import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'
import type { Role } from '../api/types'
import { homeFor, useAuth } from '../auth/useAuth'
import { ROLE_LABEL } from '../lib/format'

const NAV: { to: string; label: string; roles: Role[] }[] = [
  { to: '/chamados', label: 'Meus chamados', roles: ['cliente'] },
  { to: '/chamados/novo', label: 'Abrir chamado', roles: ['cliente'] },
  { to: '/painel', label: 'Painel', roles: ['gestor'] },
  { to: '/fila', label: 'Fila', roles: ['atendente', 'gestor'] },
  { to: '/filas', label: 'Filas e SLA', roles: ['gestor'] },
  { to: '/equipe', label: 'Equipe', roles: ['gestor'] },
]

export function Layout() {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <div className="app">
      <header className="topbar">
        <NavLink to={homeFor(user)} className="brand">
          <span className="brand-mark" aria-hidden>✓</span> Chamados
        </NavLink>
        <nav className="nav">
          {NAV.filter((item) => item.roles.includes(user.role)).map((item) => (
            <NavLink key={item.to} to={item.to} end>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          <span>
            {user.name} <small>{ROLE_LABEL[user.role]}</small>
          </span>
          <button className="btn ghost small" onClick={logout}>
            Sair
          </button>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </div>
  )
}

/** Route guard: redirects anonymous users to login and wrong roles to their home page. */
export function RequireAuth({ roles }: { roles?: Role[] }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="center muted">Carregando…</p>
  if (!user) return <Navigate to="/entrar" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user)} replace />
  return <Outlet />
}
