import type { Action, EventType, Priority, Role, SlaState, Status } from '../api/types'

export const STATUS_LABEL: Record<Status, string> = {
  aberto: 'Aberto',
  em_atendimento: 'Em atendimento',
  aguardando_cliente: 'Aguardando cliente',
  resolvido: 'Aguardando confirmação',
  fechado: 'Fechado',
}

export const PRIORITY_LABEL: Record<Priority, string> = { baixa: 'Baixa', media: 'Média', alta: 'Alta', urgente: 'Urgente' }

export const ROLE_LABEL: Record<Role, string> = { cliente: 'Cliente', atendente: 'Atendente', gestor: 'Gestor' }

export const SLA_LABEL: Record<SlaState, string> = {
  no_prazo: 'No prazo',
  em_risco: 'Em risco',
  vencido: 'Vencido',
  cumprido: 'Cumprido',
  violado: 'Fora do prazo',
  pausado: 'Pausado',
}

export const ACTION_LABEL: Record<Action, string> = {
  iniciar: 'Iniciar atendimento',
  pedir_info: 'Pedir informações',
  resposta_cliente: 'Resposta do cliente',
  propor_solucao: 'Propor solução',
  confirmar: 'Confirmar solução',
  rejeitar: 'Não resolveu',
}

const dateTime = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
export const formatDateTime = (iso: string) => dateTime.format(new Date(iso))

/** "em 3 h", "há 2 dias" — compact relative time used next to deadlines. */
export function relative(iso: string, now: Date = new Date()): string {
  const minutes = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000)
  const abs = Math.abs(minutes)
  const text = abs < 60 ? `${abs} min` : abs < 48 * 60 ? `${Math.round(abs / 60)} h` : `${Math.round(abs / 1440)} dias`
  return minutes >= 0 ? `em ${text}` : `há ${text}`
}

/** "45 min", "3 h", "2 dias" — a duration given in seconds. */
export function duration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  return minutes < 60 ? `${minutes} min` : minutes < 48 * 60 ? `${Math.round(minutes / 60)} h` : `${Math.round(minutes / 1440)} dias`
}

const percent = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 0 })
export const formatPercent = (value: number | null) => (value === null ? '—' : percent.format(value))

const decimal = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
export const formatNumber = (value: number | null, suffix = '') => (value === null ? '—' : `${decimal.format(value)}${suffix}`)

export function describeEvent(type: EventType, from: string | null, to: string | null, actor?: string): string {
  switch (type) {
    case 'criado':
      return 'abriu o chamado'
    case 'status':
      return `mudou o status: ${STATUS_LABEL[from as Status] ?? from} → ${STATUS_LABEL[to as Status] ?? to}`
    case 'atribuido':
      if (from) return `transferiu de ${from} para ${to}`
      return to === actor ? 'assumiu o chamado' : `atribuiu a ${to}`
    case 'mensagem':
      return to === 'interna' ? 'adicionou uma nota interna' : 'enviou uma mensagem'
    case 'avaliado':
      return `avaliou o atendimento com nota ${to}`
  }
}
