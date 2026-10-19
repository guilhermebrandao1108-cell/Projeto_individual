// Mirrors backend/app/schemas.py — the API contract.

export type Role = 'cliente' | 'atendente' | 'gestor'
export type Status = 'aberto' | 'em_atendimento' | 'aguardando_cliente' | 'resolvido' | 'fechado'
export type Priority = 'baixa' | 'media' | 'alta' | 'urgente'
export type SlaState = 'no_prazo' | 'em_risco' | 'vencido' | 'cumprido' | 'violado' | 'pausado'
export type Action = 'iniciar' | 'pedir_info' | 'resposta_cliente' | 'propor_solucao' | 'confirmar' | 'rejeitar'
export type EventType = 'criado' | 'status' | 'atribuido' | 'mensagem' | 'avaliado'

export interface User {
  id: number
  name: string
  email: string
  role: Role
  is_active: boolean
}

export interface UserBrief {
  id: number
  name: string
  role: Role
}

export interface Category {
  id: number
  name: string
  first_response_hours: number
  resolution_hours: number
  is_active: boolean
}

export interface Sla {
  first_response: SlaState
  first_response_due_at: string
  resolution: SlaState
  resolution_due_at: string
}

export interface TicketSummary {
  id: number
  title: string
  status: Status
  priority: Priority
  category: Category
  customer: UserBrief
  assignee: UserBrief | null
  created_at: string
  first_response_at: string | null
  resolved_at: string | null
  closed_at: string | null
  reopen_count: number
  transfer_count: number
  satisfaction: number | null
  sla_paused_seconds: number
  sla: Sla
}

export interface Message {
  id: number
  author: UserBrief
  body: string
  internal: boolean
  created_at: string
}

export interface TicketEvent {
  id: number
  actor: UserBrief
  type: EventType
  from_value: string | null
  to_value: string | null
  created_at: string
}

export interface TicketDetail extends TicketSummary {
  description: string
  satisfaction_comment: string | null
  messages: Message[]
  events: TicketEvent[]
  allowed_actions: Action[]
}

export interface Metrics {
  tickets: number
  open_tickets: number
  open_at_risk: number
  open_overdue: number
  first_response_within_sla: number | null
  first_response_p90_hours: number | null
  resolution_within_sla: number | null
  confirmed_resolution_rate: number | null
  reopen_rate: number | null
  satisfaction_coverage: number | null
  satisfaction_avg: number | null
}

export interface MetricsOverview extends Metrics {
  by_category: (Metrics & { category: string })[]
}

export interface TicketFilters {
  status?: Status
  open_only?: boolean
  category_id?: number
  assignee_id?: number
  unassigned?: boolean
  sla?: SlaState
  q?: string
  limit?: number
  offset?: number
}

export interface TicketPage {
  items: TicketSummary[]
  total: number
  limit: number
  offset: number
  open_at_risk: number
  open_overdue: number
}
