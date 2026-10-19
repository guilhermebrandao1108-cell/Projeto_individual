import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { download, query } from '../api/client'
import { useCategories, useCreateUser, useMetrics, useSaveCategory, useStaff } from '../api/hooks'
import type { Category, Metrics, Role } from '../api/types'
import { Empty, ErrorNote, Loading } from '../components/ui'
import { compare, type Delta } from '../lib/compare'
import { formatNumber, formatPercent, ROLE_LABEL } from '../lib/format'

// --- Painel ---------------------------------------------------------------------
function Tile({ label, value, hint, tone, delta }: { label: string; value: string; hint?: string; tone?: 'danger' | 'warn' | 'good'; delta?: Delta | null }) {
  return (
    <div className={`card tile ${tone ?? ''}`}>
      <span className="tile-label">{label}</span>
      <b>{value}</b>
      {delta && <span className={`delta ${delta.good === null ? '' : delta.good ? 'up' : 'down'}`}>{delta.text}</span>}
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

const PERIODS = [
  { days: 7, label: '7 dias' },
  { days: 30, label: '30 dias' },
  { days: 90, label: '90 dias' },
  { days: 0, label: 'Tudo' },
]
const DAY = 86_400_000

export function Dashboard() {
  const [days, setDays] = useState(30)
  const [now] = useState(() => Date.now()) // fixed while the page is open, so query keys stay stable
  const [exportError, setExportError] = useState<unknown>(null)
  const range = (from: number, to: number) => ({ start: new Date(from).toISOString(), end: new Date(to).toISOString() })
  const currentRange = days ? range(now - days * DAY, now) : {}
  const live = useMetrics()                                          // "Agora": every open ticket, any age
  const current = useMetrics(currentRange)
  const previous = useMetrics(days ? range(now - 2 * days * DAY, now - days * DAY) : null)
  const m = current.data
  const p = days ? previous.data : undefined
  if (live.isLoading || current.isLoading) return <Loading />
  if (!m || !live.data) return <ErrorNote error={current.error || live.error} />
  const d = (key: keyof Metrics, kind: 'rate' | 'hours' | 'score', higherIsBetter: boolean) =>
    p ? compare(m[key] as number | null, p[key] as number | null, kind, higherIsBetter) : null

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Painel</h1>
          <span className="muted small">Indicadores propostos no estudo de caso para medir o efeito do sistema</span>
        </div>
        <div className="row">
          <div className="segmented" role="group" aria-label="Período">
            {PERIODS.map((period) => (
              <button key={period.days} className={days === period.days ? 'active' : ''} aria-pressed={days === period.days}
                      onClick={() => setDays(period.days)}>
                {period.label}
              </button>
            ))}
          </div>
          <button className="btn" title="Um chamado por linha, sem dados pessoais: entrada de python -m atendimento piloto"
                  onClick={() => { setExportError(null); download(`/metrics/export.csv${query(currentRange)}`, 'chamados.csv').catch(setExportError) }}>
            Exportar CSV
          </button>
        </div>
      </div>
      <ErrorNote error={exportError} />

      <h2 className="section">Agora</h2>
      <div className="tiles">
        <Tile label="Chamados abertos" value={String(live.data.open_tickets)} hint={`de ${live.data.tickets} no total`} />
        <Tile label="Em risco" value={String(live.data.open_at_risk)} hint="perto de vencer o prazo" tone={live.data.open_at_risk ? 'warn' : undefined} />
        <Tile label="Vencidos" value={String(live.data.open_overdue)} hint="prazo já estourado" tone={live.data.open_overdue ? 'danger' : 'good'} />
      </div>
      {(live.data.open_overdue > 0 || live.data.open_at_risk > 0) && (
        <p><Link to="/fila">Ver na fila →</Link></p>
      )}

      <h2 className="section">
        Prazos <small className="muted">{days ? `chamados criados nos últimos ${days} dias · ${m.tickets}` : `todos os chamados · ${m.tickets}`}</small>
      </h2>
      <div className="tiles">
        <Tile label="1ª resposta no prazo" value={formatPercent(m.first_response_within_sla)} delta={d('first_response_within_sla', 'rate', true)}
              tone={tone(m.first_response_within_sla, .9, .7)} hint="vencidos sem resposta contam como falha" />
        <Tile label="p90 da 1ª resposta" value={formatNumber(m.first_response_p90_hours, ' h')} delta={d('first_response_p90_hours', 'hours', false)}
              hint="90% respondidos até aqui" />
        <Tile label="Resolução no prazo" value={formatPercent(m.resolution_within_sla)} delta={d('resolution_within_sla', 'rate', true)}
              tone={tone(m.resolution_within_sla, .9, .7)} />
      </div>

      <h2 className="section">Resolução de verdade</h2>
      <div className="tiles">
        <Tile label="Solução confirmada" value={formatPercent(m.confirmed_resolution_rate)} delta={d('confirmed_resolution_rate', 'rate', true)}
              hint="confirmadas pelo cliente ÷ propostas" tone={tone(m.confirmed_resolution_rate, .8, .6)} />
        <Tile label="Reabertura" value={formatPercent(m.reopen_rate)} hint="soluções rejeitadas pelo cliente" delta={d('reopen_rate', 'rate', false)}
              tone={m.reopen_rate === null ? undefined : m.reopen_rate <= .1 ? 'good' : m.reopen_rate > .25 ? 'danger' : 'warn'} />
        <Tile label="Avaliação" value={formatNumber(m.satisfaction_avg, ' / 5')} delta={d('satisfaction_avg', 'score', true)}
              hint={`${formatPercent(m.satisfaction_coverage)} dos fechados avaliados`} />
      </div>

      <h2 className="section">Por fila</h2>
      {!m.by_category.length ? (
        <Empty>Sem chamados no período.</Empty>
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
