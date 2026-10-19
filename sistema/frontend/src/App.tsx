import { Navigate, Route, Routes } from 'react-router-dom'
import { homeFor, useAuth } from './auth/useAuth'
import { Layout, RequireAuth } from './components/Layout'
import { MyTickets, NewTicket } from './pages/Customer'
import { Login, Register } from './pages/Login'
import { Categories, Dashboard, Team } from './pages/Manager'
import { Queue } from './pages/Queue'
import { TicketPage } from './pages/TicketPage'

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <Navigate to={user ? homeFor(user) : '/entrar'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      <Route path="/cadastro" element={<Register />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route path="/chamados/:id" element={<TicketPage />} />
          <Route element={<RequireAuth roles={['cliente']} />}>
            <Route path="/chamados" element={<MyTickets />} />
            <Route path="/chamados/novo" element={<NewTicket />} />
          </Route>
          <Route element={<RequireAuth roles={['atendente', 'gestor']} />}>
            <Route path="/fila" element={<Queue />} />
          </Route>
          <Route element={<RequireAuth roles={['gestor']} />}>
            <Route path="/painel" element={<Dashboard />} />
            <Route path="/filas" element={<Categories />} />
            <Route path="/equipe" element={<Team />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
