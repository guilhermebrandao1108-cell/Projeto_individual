import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { homeFor, useAuth } from '../auth/useAuth'
import { ErrorNote } from '../components/ui'

// Accounts created by `python -m app.seed` (backend). Shown only in development builds.
const DEMO = [
  { label: 'Cliente', email: 'ana@demo.com' },
  { label: 'Atendente', email: 'lucas@demo.com' },
  { label: 'Gestor', email: 'gestor@demo.com' },
]
const DEMO_PASSWORD = 'demo12345'

export function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const from = (useLocation().state as { from?: string } | null)?.from
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={homeFor(user)} replace />

  async function submit(e: FormEvent, credentials = { email, password }) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const me = await login(credentials.email, credentials.password)
      navigate(from ?? homeFor(me), { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <form className="card auth-card" onSubmit={submit}>
        <h1>Entrar</h1>
        <p className="muted">Gestão de chamados com prazos e confirmação de solução.</p>
        <label>
          E-mail
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Senha
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <ErrorNote error={error} />
        <button className="btn primary" disabled={busy}>
          {busy ? 'Entrando…' : 'Entrar'}
        </button>
        <p className="muted small">
          Não tem conta? <Link to="/cadastro">Cadastre-se</Link>
        </p>
        {import.meta.env.DEV && (
          <div className="demo">
            <span className="small muted">Contas de demonstração:</span>
            <div className="row">
              {DEMO.map((d) => (
                <button key={d.email} type="button" className="btn small" disabled={busy}
                        onClick={(e) => submit(e, { email: d.email, password: DEMO_PASSWORD })}>
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </form>
    </div>
  )
}

export function Register() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={homeFor(user)} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register(form.name, form.email, form.password)
      navigate('/chamados/novo', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const set = (field: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [field]: e.target.value })
  return (
    <div className="auth">
      <form className="card auth-card" onSubmit={submit}>
        <h1>Criar conta</h1>
        <label>
          Nome
          <input required minLength={2} value={form.name} onChange={set('name')} />
        </label>
        <label>
          E-mail
          <input type="email" required value={form.email} onChange={set('email')} />
        </label>
        <label>
          Senha <small className="muted">(mínimo 8 caracteres)</small>
          <input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set('password')} />
        </label>
        <ErrorNote error={error} />
        <button className="btn primary" disabled={busy}>
          {busy ? 'Criando…' : 'Criar conta'}
        </button>
        <p className="muted small">
          Já tem conta? <Link to="/entrar">Entrar</Link>
        </p>
      </form>
    </div>
  )
}
