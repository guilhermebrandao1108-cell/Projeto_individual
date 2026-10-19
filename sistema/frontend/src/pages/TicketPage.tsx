import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAssign, useConfirm, useReject, useResolve, useSendMessage, useStaff, useTicket, useTicketAction } from '../api/hooks'
import type { Message, TicketDetail, TicketEvent, User } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { PriorityBadge, SlaStateBadge, StatusBadge } from '../components/Badges'
import { ErrorNote, Loading, Rating } from '../components/ui'
import { describeEvent, duration, formatDateTime, relative } from '../lib/format'

export function TicketPage() {
  const id = Number(useParams().id)
  const { user } = useAuth()
  const { data: ticket, isLoading, error } = useTicket(id)

  if (isLoading) return <Loading />
  if (!ticket || !user) return <ErrorNote error={error} />
  const isStaff = user.role !== 'cliente'

  return (
    <>
      <Link to={isStaff ? '/fila' : '/chamados'} className="back">← Voltar</Link>
      <div className="page-head">
        <div>
          <h1>#{ticket.id} · {ticket.title}</h1>
          <div className="row">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
            <span className="muted small">{ticket.category.name}</span>
          </div>
        </div>
      </div>

      <div className="ticket-layout">
        <section>
          {ticket.status === 'resolvido' && !isStaff && <ConfirmPanel ticket={ticket} />}
          {ticket.status === 'fechado' && <ClosedPanel ticket={ticket} />}
          <Timeline ticket={ticket} isStaff={isStaff} />
          {ticket.status !== 'fechado' && <Composer ticket={ticket} user={user} />}
        </section>
        <aside className="side">
          <Details ticket={ticket} />
          {isStaff && ticket.status !== 'fechado' && <Assignment ticket={ticket} user={user} />}
        </aside>
      </div>
    </>
  )
}

type Item = { kind: 'message'; at: string; message: Message } | { kind: 'event'; at: string; event: TicketEvent }

function Timeline({ ticket, isStaff }: { ticket: TicketDetail; isStaff: boolean }) {
  // Message events duplicate the message itself; customers only see status changes, not internal routing.
  const events = ticket.events.filter((e) => e.type !== 'mensagem' && (isStaff || e.type !== 'atribuido'))
  const items: Item[] = [
    ...ticket.messages.map((m) => ({ kind: 'message' as const, at: m.created_at, message: m })),
    ...events.map((e) => ({ kind: 'event' as const, at: e.created_at, event: e })),
  ].sort((a, b) => a.at.localeCompare(b.at))

  return (
    <ol className="timeline">
      <li className="msg customer">
        <div className="msg-head">
          <strong>{ticket.customer.name}</strong> <span className="muted small">{formatDateTime(ticket.created_at)}</span>
        </div>
        <p>{ticket.description}</p>
      </li>
      {items.map((item) =>
        item.kind === 'message' ? (
          <li key={`m${item.message.id}`}
              className={`msg ${item.message.internal ? 'internal' : item.message.author.role === 'cliente' ? 'customer' : 'staff'}`}>
            <div className="msg-head">
              <strong>{item.message.author.name}</strong>
              {item.message.internal && <span className="badge internal-tag">Nota interna</span>}
              <span className="muted small">{formatDateTime(item.message.created_at)}</span>
            </div>
            <p>{item.message.body}</p>
          </li>
        ) : item.event.type === 'criado' ? null : (
          <li key={`e${item.event.id}`} className="event">
            <span>
              <strong>{item.event.actor.name}</strong> {describeEvent(item.event.type, item.event.from_value, item.event.to_value, item.event.actor.name)}
            </span>
            <span className="muted small">{formatDateTime(item.event.created_at)}</span>
          </li>
        ),
      )}
    </ol>
  )
}

function Composer({ ticket, user }: { ticket: TicketDetail; user: User }) {
  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const send = useSendMessage(ticket.id)
  const act = useTicketAction(ticket.id)
  const resolve = useResolve(ticket.id)
  const isStaff = user.role !== 'cliente'
  const can = (a: string) => ticket.allowed_actions.includes(a as never)
  const busy = send.isPending || act.isPending || resolve.isPending
  // Clear only if the box still holds what was sent: the user may already be typing the next message.
  const clearIf = (sent: string) => ({ onSuccess: () => { setBody((b) => (b.trim() === sent ? '' : b)); setInternal(false) } })
  const text = body.trim()

  return (
    <div className="card composer">
      <textarea rows={4} value={body} onChange={(e) => setBody(e.target.value)}
                placeholder={isStaff ? 'Escreva para o cliente ou uma nota interna…' : 'Escreva uma mensagem para a equipe…'} />
      <ErrorNote error={send.error || act.error || resolve.error} />
      <div className="row between">
        {isStaff ? (
          <label className="check">
            <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} /> Nota interna (o cliente não vê)
          </label>
        ) : <span />}
        <div className="row">
          {can('iniciar') && (
            <button className="btn" disabled={busy} onClick={() => act.mutate({ action: 'iniciar' })}>Iniciar atendimento</button>
          )}
          {can('pedir_info') && (
            <button className="btn" disabled={busy || !text || internal} title="Envia a mensagem e aguarda o cliente"
                    onClick={() => act.mutate({ action: 'pedir_info', message: text }, clearIf(text))}>
              Pedir informações
            </button>
          )}
          {can('propor_solucao') && (
            <button className="btn success" disabled={busy || text.length < 5 || internal} title="Envia a solução; o cliente confirma se resolveu"
                    onClick={() => resolve.mutate({ message: text }, clearIf(text))}>
              Propor solução
            </button>
          )}
          <button className="btn primary" disabled={busy || !text} onClick={() => send.mutate({ body: text, internal }, clearIf(text))}>
            Enviar
          </button>
        </div>
      </div>
    </div>
  )
}

/** The customer, not the agent, decides whether the problem is solved. */
function ConfirmPanel({ ticket }: { ticket: TicketDetail }) {
  const [mode, setMode] = useState<'ask' | 'yes' | 'no'>('ask')
  const [rating, setRating] = useState<number | null>(null)
  const [comment, setComment] = useState('')
  const confirm = useConfirm(ticket.id)
  const reject = useReject(ticket.id)

  return (
    <div className="card confirm">
      <h2>O seu problema foi resolvido?</h2>
      <p className="muted">A equipe propôs uma solução. O chamado só é encerrado com a sua confirmação.</p>
      {mode === 'ask' && (
        <div className="row">
          <button className="btn success" onClick={() => setMode('yes')}>Sim, foi resolvido</button>
          <button className="btn danger" onClick={() => setMode('no')}>Não, continuo com o problema</button>
        </div>
      )}
      {mode === 'yes' && (
        <>
          <span>Como foi o atendimento? <small className="muted">(opcional)</small></span>
          <Rating value={rating} onChange={setRating} />
          <textarea rows={2} placeholder="Comentário (opcional)" value={comment} onChange={(e) => setComment(e.target.value)} />
          <ErrorNote error={confirm.error} />
          <div className="row">
            <button className="btn ghost" onClick={() => setMode('ask')}>Voltar</button>
            <button className="btn success" disabled={confirm.isPending}
                    onClick={() => confirm.mutate({ satisfaction: rating, comment: comment.trim() || null })}>
              Confirmar e encerrar
            </button>
          </div>
        </>
      )}
      {mode === 'no' && (
        <>
          <textarea rows={3} placeholder="Conte o que ainda não funciona…" value={comment} onChange={(e) => setComment(e.target.value)} />
          <ErrorNote error={reject.error} />
          <div className="row">
            <button className="btn ghost" onClick={() => setMode('ask')}>Voltar</button>
            <button className="btn danger" disabled={reject.isPending || comment.trim().length < 5}
                    onClick={() => reject.mutate({ message: comment.trim() })}>
              Reabrir chamado
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function ClosedPanel({ ticket }: { ticket: TicketDetail }) {
  return (
    <div className="card closed">
      <strong>Solução confirmada pelo cliente</strong> em {formatDateTime(ticket.closed_at!)}
      {ticket.satisfaction ? (
        <div>
          <span className="stars" aria-label={`Nota ${ticket.satisfaction} de 5`}>
            {'★'.repeat(ticket.satisfaction)}<span className="muted">{'★'.repeat(5 - ticket.satisfaction)}</span>
          </span>
          {ticket.satisfaction_comment && <q> {ticket.satisfaction_comment}</q>}
        </div>
      ) : (
        <div className="muted small">Sem avaliação.</div>
      )}
    </div>
  )
}

function Details({ ticket }: { ticket: TicketDetail }) {
  const pending = ticket.status !== 'fechado'
  return (
    <div className="card">
      <h3>Prazos</h3>
      <dl className="details">
        <dt>1ª resposta</dt>
        <dd>
          <SlaStateBadge state={ticket.sla.first_response} />
          <div className="muted small">
            {ticket.first_response_at ? `respondido ${formatDateTime(ticket.first_response_at)}` : `até ${formatDateTime(ticket.sla.first_response_due_at)} (${relative(ticket.sla.first_response_due_at)})`}
          </div>
        </dd>
        <dt>Resolução</dt>
        <dd>
          <SlaStateBadge state={ticket.sla.resolution} />
          <div className="muted small">
            {ticket.resolved_at ? `solução proposta ${formatDateTime(ticket.resolved_at)}`
              : ticket.sla.resolution === 'pausado' ? 'parado enquanto aguarda o cliente'
              : pending ? `até ${formatDateTime(ticket.sla.resolution_due_at)} (${relative(ticket.sla.resolution_due_at)})` : ''}
          </div>
          {ticket.sla_paused_seconds > 0 && (
            <div className="muted small">prazo estendido em {duration(ticket.sla_paused_seconds)} por espera do cliente</div>
          )}
        </dd>
      </dl>
      <h3>Detalhes</h3>
      <dl className="details">
        <dt>Cliente</dt><dd>{ticket.customer.name}</dd>
        <dt>Responsável</dt><dd>{ticket.assignee?.name ?? '—'}</dd>
        <dt>Aberto em</dt><dd>{formatDateTime(ticket.created_at)}</dd>
        {ticket.reopen_count > 0 && (<><dt>Reaberturas</dt><dd>{ticket.reopen_count}</dd></>)}
        {ticket.transfer_count > 0 && (<><dt>Transferências</dt><dd>{ticket.transfer_count}</dd></>)}
      </dl>
    </div>
  )
}

function Assignment({ ticket, user }: { ticket: TicketDetail; user: User }) {
  const assign = useAssign(ticket.id)
  const staff = useStaff(user.role === 'gestor')
  if (user.role === 'atendente') {
    if (ticket.assignee) return null
    return (
      <div className="card">
        <button className="btn primary full" disabled={assign.isPending} onClick={() => assign.mutate({ assignee_id: user.id })}>
          Assumir chamado
        </button>
        <ErrorNote error={assign.error} />
      </div>
    )
  }
  return (
    <div className="card">
      <h3>{ticket.assignee ? 'Transferir' : 'Atribuir'}</h3>
      <select value={ticket.assignee?.id ?? ''} disabled={assign.isPending}
              onChange={(e) => e.target.value && assign.mutate({ assignee_id: Number(e.target.value) })}>
        <option value="" disabled>Escolha um responsável…</option>
        {staff.data?.map((u) => (
          <option key={u.id} value={u.id}>{u.name}</option>
        ))}
      </select>
      <ErrorNote error={assign.error} />
    </div>
  )
}
