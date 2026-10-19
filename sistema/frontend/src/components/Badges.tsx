import type { Priority, Sla, SlaState, Status } from '../api/types'
import { PRIORITY_LABEL, relative, SLA_LABEL, STATUS_LABEL } from '../lib/format'

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status]}</span>
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={`badge priority-${priority}`}>{PRIORITY_LABEL[priority]}</span>
}

const PENDING: SlaState[] = ['no_prazo', 'em_risco', 'vencido', 'pausado']
const COUNTING: SlaState[] = ['no_prazo', 'em_risco', 'vencido']

/** Shows the target that matters now: first response until it is met, then resolution. */
export function SlaBadge({ sla, closed }: { sla: Sla; closed?: boolean }) {
  const firstPending = PENDING.includes(sla.first_response)
  const [label, state, due] = firstPending
    ? ['1ª resposta', sla.first_response, sla.first_response_due_at]
    : ['Resolução', sla.resolution, sla.resolution_due_at]
  const pending = COUNTING.includes(state) && !closed
  return (
    <span className={`sla sla-${state}`} title={`${label}: ${SLA_LABEL[state]}`}>
      <span className="sla-dot" aria-hidden />
      {label} · {SLA_LABEL[state]}
      {pending && <span className="sla-due"> {state === 'vencido' ? `venceu ${relative(due)}` : `vence ${relative(due)}`}</span>}
      {state === 'pausado' && <span className="sla-due"> aguardando o cliente</span>}
    </span>
  )
}

export function SlaStateBadge({ state }: { state: SlaState }) {
  return (
    <span className={`sla sla-${state}`}>
      <span className="sla-dot" aria-hidden />
      {SLA_LABEL[state]}
    </span>
  )
}
