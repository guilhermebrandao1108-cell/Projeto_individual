// Server state lives in TanStack Query: components never fetch directly.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { patch, post, query, request } from './client'
import type { Action, Category, MetricsOverview, Priority, Role, TicketDetail, TicketFilters, TicketSummary, User } from './types'

export const keys = {
  tickets: (filters?: TicketFilters) => ['tickets', filters ?? {}] as const,
  ticket: (id: number) => ['ticket', id] as const,
  categories: ['categories'] as const,
  staff: ['staff'] as const,
  metrics: ['metrics'] as const,
}

// Ticket lists refresh periodically so SLA states ("em risco", "vencido") stay current.
export const useTickets = (filters: TicketFilters = {}) =>
  useQuery({
    queryKey: keys.tickets(filters),
    queryFn: () => request<TicketSummary[]>(`/tickets${query({ ...filters })}`),
    refetchInterval: 60_000,
  })

export const useTicket = (id: number) =>
  useQuery({ queryKey: keys.ticket(id), queryFn: () => request<TicketDetail>(`/tickets/${id}`) })

export const useCategories = (includeInactive = false) =>
  useQuery({
    queryKey: [...keys.categories, includeInactive],
    queryFn: () => request<Category[]>(`/categories${query({ include_inactive: includeInactive })}`),
  })

export const useStaff = (enabled: boolean) =>
  useQuery({
    queryKey: keys.staff,
    enabled,
    queryFn: async () => (await request<User[]>('/users')).filter((u) => u.role !== 'cliente' && u.is_active),
  })

export const useMetrics = () => useQuery({ queryKey: keys.metrics, queryFn: () => request<MetricsOverview>('/metrics/overview') })

/** Every ticket mutation returns the updated detail: write it to the cache and refresh lists. */
function useTicketMutation<V>(id: number, fn: (vars: V) => Promise<TicketDetail>) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (ticket) => {
      client.setQueryData(keys.ticket(id), ticket)
      client.invalidateQueries({ queryKey: ['tickets'] })
      client.invalidateQueries({ queryKey: keys.metrics })
    },
  })
}

export const useSendMessage = (id: number) =>
  useTicketMutation(id, (v: { body: string; internal: boolean }) => post<TicketDetail>(`/tickets/${id}/messages`, v))

export const useTicketAction = (id: number) =>
  useTicketMutation(id, (v: { action: Extract<Action, 'iniciar' | 'pedir_info'>; message?: string }) =>
    post<TicketDetail>(`/tickets/${id}/actions`, v))

export const useResolve = (id: number) =>
  useTicketMutation(id, (v: { message: string }) => post<TicketDetail>(`/tickets/${id}/resolve`, v))

export const useConfirm = (id: number) =>
  useTicketMutation(id, (v: { satisfaction: number | null; comment: string | null }) => post<TicketDetail>(`/tickets/${id}/confirm`, v))

export const useReject = (id: number) =>
  useTicketMutation(id, (v: { message: string }) => post<TicketDetail>(`/tickets/${id}/reject`, v))

export const useAssign = (id: number) =>
  useTicketMutation(id, (v: { assignee_id: number }) => post<TicketDetail>(`/tickets/${id}/assign`, v))

export function useCreateTicket() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (v: { title: string; description: string; category_id: number; priority: Priority }) =>
      post<TicketDetail>('/tickets', v),
    onSuccess: () => client.invalidateQueries({ queryKey: ['tickets'] }),
  })
}

export function useSaveCategory() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Category> & { id?: number }) =>
      id ? patch<Category>(`/categories/${id}`, data) : post<Category>('/categories', data),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.categories }),
  })
}

export function useCreateUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (v: { name: string; email: string; password: string; role: Role }) => post<User>('/users', v),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.staff }),
  })
}
