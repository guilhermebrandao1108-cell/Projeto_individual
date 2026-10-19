import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useCategories, useCreateTicket, useTickets } from '../api/hooks'
import type { Priority } from '../api/types'
import { StatusBadge } from '../components/Badges'
import { Empty, ErrorNote, Loading } from '../components/ui'
import { formatDateTime, PRIORITY_LABEL } from '../lib/format'

export function MyTickets() {
  const { data, isLoading, error } = useTickets()
  const waitingMe = data?.filter((t) => t.status === 'resolvido' || t.status === 'aguardando_cliente') ?? []

  return (
    <>
      <div className="page-head">
        <h1>Meus chamados</h1>
        <Link className="btn primary" to="/chamados/novo">
          Abrir chamado
        </Link>
      </div>
      {waitingMe.length > 0 && (
        <p className="notice">
          {waitingMe.length === 1 ? '1 chamado precisa' : `${waitingMe.length} chamados precisam`} da sua resposta.
        </p>
      )}
      <ErrorNote error={error} />
      {isLoading ? (
        <Loading />
      ) : !data?.length ? (
        <Empty>
          Você ainda não abriu chamados. <Link to="/chamados/novo">Abrir o primeiro</Link>
        </Empty>
      ) : (
        <ul className="ticket-cards">
          {data.map((t) => (
            <li key={t.id}>
              <Link to={`/chamados/${t.id}`} className="card ticket-card">
                <div className="row between">
                  <strong>
                    #{t.id} · {t.title}
                  </strong>
                  <StatusBadge status={t.status} />
                </div>
                <span className="muted small">
                  {t.category.name} · aberto em {formatDateTime(t.created_at)}
                  {t.assignee && ` · com ${t.assignee.name}`}
                </span>
                {(t.status === 'resolvido' || t.status === 'aguardando_cliente') && (
                  <span className="action-hint">
                    {t.status === 'resolvido' ? 'Confirme se o problema foi resolvido →' : 'A equipe pediu mais informações →'}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}

export function NewTicket() {
  const navigate = useNavigate()
  const categories = useCategories()
  const create = useCreateTicket()
  const [form, setForm] = useState({ title: '', description: '', category_id: 0, priority: 'media' as Priority })

  function submit(e: FormEvent) {
    e.preventDefault()
    create.mutate(form, { onSuccess: (t) => navigate(`/chamados/${t.id}`) })
  }

  const selected = categories.data?.find((c) => c.id === form.category_id)
  return (
    <form className="card form narrow" onSubmit={submit}>
      <h1>Abrir chamado</h1>
      <label>
        Assunto
        <select required value={form.category_id || ''} onChange={(e) => setForm({ ...form, category_id: Number(e.target.value) })}>
          <option value="" disabled>
            Selecione…
          </option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {selected && (
        <p className="muted small">
          Primeira resposta em até {selected.first_response_hours} h · solução em até {selected.resolution_hours} h
        </p>
      )}
      <label>
        Título
        <input required minLength={5} maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
               placeholder="Ex.: Cobrança em duplicidade" />
      </label>
      <label>
        Descreva o problema
        <textarea required minLength={10} rows={6} value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="O que aconteceu, quando, e o que você já tentou." />
      </label>
      <label>
        Prioridade
        <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value as Priority })}>
          {(Object.keys(PRIORITY_LABEL) as Priority[]).map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABEL[p]}
            </option>
          ))}
        </select>
      </label>
      <ErrorNote error={create.error} />
      <button className="btn primary" disabled={create.isPending}>
        {create.isPending ? 'Enviando…' : 'Abrir chamado'}
      </button>
    </form>
  )
}
