import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useCategories, useCreateUser, useMetrics, useSaveCategory, useStaff } from '../api/hooks'
import type { Category, Metrics, Role } from '../api/types'
import { Empty, ErrorNote, Loading } from '../components/ui'
import { formatNumber, formatPercent, ROLE_LABEL } from '../lib/format'

// --- Painel ---------------------------------------------------------------------
function Tile({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: 'danger' | 'warn' | 'good' }) {
  return (
    <div className={`card tile ${tone ?? ''}`}>
      <span className="tile-label">{label}</span>
      <b>{value}</b>
      {hint && <span className="muted small">{hint}</span>}
    </div>
  )
}

function Bar({ value }: { value: number | null }) {
  if (value === null) return <span className="muted">—</span>
  return (
    <div className="bar" title={formatPercent(value)}>
      <span style={{ width: `${Math.round(value * 100)}%` }} />
      <em>{formatPercent(value)}</em>
    </div>
  )
}

const tone = (value: number | null, good: number, bad: number) =>
  value === null ? undefined : value >= good ? 'good' : value < bad ? 'danger' : 'warn'

export function Dashboard() {
  const { data: m, isLoading, error } = useMetrics()
  if (isLoading) return <Loading />
  if (!m) return <ErrorNote error={error} />

  return (
    <>
      <div className="page-head">
        <h1>Painel</h1>
        <span className="muted small">Indicadores propostos no estudo de caso para medir o efeito do sistema</span>
      </div>

      <h2 className="section">Agora</h2>
      <div className="tiles">
        <Tile label="Chamados abertos" value={String(m.open_tickets)} hint={`de ${m.tickets} no total`} />
        <Tile label="Em risco" value={String(m.open_at_risk)} hint="perto de vencer o prazo" tone={m.open_at_risk ? 'warn' : undefined} />
        <Tile label="Vencidos" value={String(m.open_overdue)} hint="prazo já estourado" tone={m.open_overdue ? 'danger' : 'good'} />
      </div>
      {(m.open_overdue > 0 || m.open_at_risk > 0) && (
        <p><Link to="/fila">Ver na fila →</Link></p>
      )}

      <h2 className="section">Prazos</h2>
      <div className="tiles">
        <Tile label="1ª resposta no prazo" value={formatPercent(m.first_response_within_sla)}
              tone={tone(m.first_response_within_sla, .9, .7)} hint="vencidos sem resposta contam como falha" />
        <Tile label="p90 da 1ª resposta" value={formatNumber(m.first_response_p90_hours, ' h')} hint="90% respondidos até aqui" />
        <Tile label="Resolução no prazo" value={formatPercent(m.resolution_within_sla)} tone={tone(m.resolution_within_sla, .9, .7)} />
      </div>

      <h2 className="section">Resolução de verdade</h2>
      <div className="tiles">
        <Tile label="Solução confirmada" value={formatPercent(m.confirmed_resolution_rate)}
              hint="confirmadas pelo cliente ÷ propostas" tone={tone(m.confirmed_resolution_rate, .8, .6)} />
        <Tile label="Reabertura" value={formatPercent(m.reopen_rate)} hint="soluções rejeitadas pelo cliente"
              tone={m.reopen_rate === null ? undefined : m.reopen_rate <= .1 ? 'good' : m.reopen_rate > .25 ? 'danger' : 'warn'} />
        <Tile label="Avaliação" value={formatNumber(m.satisfaction_avg, ' / 5')}
              hint={`${formatPercent(m.satisfaction_coverage)} dos fechados avaliados`} />
      </div>

      <h2 className="section">Por fila</h2>
      {!m.by_category.length ? (
        <Empty>Sem chamados ainda.</Empty>
      ) : (
        <div className="table-wrap card">
          <table className="table">
            <thead>
              <tr>
                <th>Fila</th>
                <th className="num">Chamados</th>
                <th className="num">Abertos</th>
                <th className="num">Vencidos</th>
                <th>1ª resposta no prazo</th>
                <th>Solução confirmada</th>
                <th className="num">Nota</th>
              </tr>
            </thead>
            <tbody>
              {m.by_category.map((c: Metrics & { category: string }) => (
                <tr key={c.category}>
                  <td><strong>{c.category}</strong></td>
                  <td className="num">{c.tickets}</td>
                  <td className="num">{c.open_tickets}</td>
                  <td className={`num ${c.open_overdue ? 'text-danger' : ''}`}>{c.open_overdue}</td>
                  <td><Bar value={c.first_response_within_sla} /></td>
                  <td><Bar value={c.confirmed_resolution_rate} /></td>
                  <td className="num">{formatNumber(c.satisfaction_avg)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

// --- Filas e SLA ----------------------------------------------------------------
function CategoryRow({ category }: { category: Category }) {
  const save = useSaveCategory()
  const [draft, setDraft] = useState(category)
  const dirty = JSON.stringify(draft) !== JSON.stringify(category)
  return (
    <tr>
      <td><input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
      <td><input type="number" min={1} value={draft.first_response_hours} onChange={(e) => setDraft({ ...draft, first_response_hours: Number(e.target.value) })} /></td>
      <td><input type="number" min={1} value={draft.resolution_hours} onChange={(e) => setDraft({ ...draft, resolution_hours: Number(e.target.value) })} /></td>
      <td>
        <label className="check">
          <input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} /> Ativa
        </label>
      </td>
      <td>
        <button className="btn small primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>Salvar</button>
        <ErrorNote error={save.error} />
      </td>
    </tr>
  )
}

export function Categories() {
  const { data, isLoading, error } = useCategories(true)
  const save = useSaveCategory()
  const empty = { name: '', first_response_hours: 4, resolution_hours: 48 }
  const [form, setForm] = useState(empty)

  function submit(e: FormEvent) {
    e.preventDefault()
    save.mutate(form, { onSuccess: () => setForm(empty) })
  }

  return (
    <>
      <div className="page-head">
        <h1>Filas e SLA</h1>
        <span className="muted small">Mudanças valem para chamados novos; os abertos mantêm o prazo combinado.</span>
      </div>
      <ErrorNote error={error} />
      {isLoading ? <Loading /> : (
        <div className="table-wrap card">
          <table className="table form-table">
            <thead>
              <tr><th>Fila</th><th>1ª resposta (h)</th><th>Resolução (h)</th><th /><th /></tr>
            </thead>
            <tbody>
              {data?.map((c) => <CategoryRow key={`${c.id}-${c.name}-${c.first_response_hours}-${c.resolution_hours}-${c.is_active}`} category={c} />)}
            </tbody>
          </table>
        </div>
      )}
      <form className="card form inline-form" onSubmit={submit}>
        <h3>Nova fila</h3>
        <label>Nome<input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>1ª resposta (h)<input type="number" min={1} required value={form.first_response_hours} onChange={(e) => setForm({ ...form, first_response_hours: Number(e.target.value) })} /></label>
        <label>Resolução (h)<input type="number" min={1} required value={form.resolution_hours} onChange={(e) => setForm({ ...form, resolution_hours: Number(e.target.value) })} /></label>
        <button className="btn primary" disabled={save.isPending}>Criar</button>
        <ErrorNote error={save.error} />
      </form>
    </>
  )
}

// --- Equipe ---------------------------------------------------------------------
export function Team() {
  const staff = useStaff(true)
  const create = useCreateUser()
  const empty = { name: '', email: '', password: '', role: 'atendente' as Role }
  const [form, setForm] = useState(empty)

  function submit(e: FormEvent) {
    e.preventDefault()
    create.mutate(form, { onSuccess: () => setForm(empty) })
  }

  return (
    <>
      <div className="page-head"><h1>Equipe</h1></div>
      {staff.isLoading ? <Loading /> : (
        <div className="table-wrap card">
          <table className="table">
            <thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th></tr></thead>
            <tbody>
              {staff.data?.map((u) => (
                <tr key={u.id}><td>{u.name}</td><td>{u.email}</td><td>{ROLE_LABEL[u.role]}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form className="card form inline-form" onSubmit={submit}>
        <h3>Adicionar à equipe</h3>
        <label>Nome<input required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>E-mail<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label>Senha inicial<input type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
        <label>Perfil
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            <option value="atendente">Atendente</option>
            <option value="gestor">Gestor</option>
          </select>
        </label>
        <button className="btn primary" disabled={create.isPending}>Adicionar</button>
        <ErrorNote error={create.error} />
      </form>
    </>
  )
}
