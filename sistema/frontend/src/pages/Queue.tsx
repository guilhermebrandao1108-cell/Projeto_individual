import { useDeferredValue, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCategories, useStaff, useTickets } from '../api/hooks'
import type { SlaState, Status, TicketFilters } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { PriorityBadge, SlaBadge, StatusBadge } from '../components/Badges'
import { Empty, ErrorNote, Loading, Pager } from '../components/ui'
import { SLA_LABEL, STATUS_LABEL } from '../lib/format'

const PAGE_SIZE = 25

export function Queue() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const categories = useCategories()
  const staff = useStaff(user?.role === 'gestor')
  const [filters, setFilters] = useState<TicketFilters>({ open_only: true })
  const [offset, setOffset] = useState(0)
  const q = useDeferredValue(filters.q)
  // Filtering, counting and paging happen on the server (in SQL).
  const tickets = useTickets({ ...filters, q, limit: PAGE_SIZE, offset })

  const page = tickets.data
  const shown = page?.items ?? []
  const set = (patch: Partial<TicketFilters>) => {
    setFilters({ ...filters, ...patch })
    setOffset(0)
  }

  return (
    <>
      <div className="page-head">
        <h1>Fila de atendimento</h1>
        <div className="row">
          <button className={`chip danger ${filters.sla === 'vencido' ? 'active' : ''}`}
                  onClick={() => set({ sla: filters.sla === 'vencido' ? undefined : 'vencido' })}>
            {page?.open_overdue ?? 0} vencidos
          </button>
          <button className={`chip warn ${filters.sla === 'em_risco' ? 'active' : ''}`}
                  onClick={() => set({ sla: filters.sla === 'em_risco' ? undefined : 'em_risco' })}>
            {page?.open_at_risk ?? 0} em risco
          </button>
        </div>
      </div>

      <div className="filters card">
        <input type="search" placeholder="Buscar no título ou descrição…" value={filters.q ?? ''} onChange={(e) => set({ q: e.target.value })} />
        <select value={filters.status ?? ''} onChange={(e) => set({ status: (e.target.value || undefined) as Status | undefined })}>
          <option value="">Todos os status</option>
          {(Object.keys(STATUS_LABEL) as Status[]).map((s) => (
            <option key={s} value={s}>{STATUS_LABEL[s]}</option>
          ))}
        </select>
        <select value={filters.category_id ?? ''} onChange={(e) => set({ category_id: Number(e.target.value) || undefined })}>
          <option value="">Todas as filas</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
        <select value={filters.sla ?? ''} onChange={(e) => set({ sla: (e.target.value || undefined) as SlaState | undefined })}>
          <option value="">Qualquer SLA</option>
          {(Object.keys(SLA_LABEL) as SlaState[]).map((s) => (
            <option key={s} value={s}>{SLA_LABEL[s]}</option>
          ))}
        </select>
        {user?.role === 'gestor' ? (
          <select value={filters.unassigned ? 'none' : filters.assignee_id ?? ''}
                  onChange={(e) => e.target.value === 'none'
                    ? set({ unassigned: true, assignee_id: undefined })
                    : set({ unassigned: false, assignee_id: Number(e.target.value) || undefined })}>
            <option value="">Qualquer responsável</option>
            <option value="none">Sem responsável</option>
            {staff.data?.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        ) : (
          <label className="check">
            <input type="checkbox" checked={filters.assignee_id === user?.id}
                   onChange={(e) => set({ assignee_id: e.target.checked ? user?.id : undefined, unassigned: false })} />
            Só os meus
          </label>
        )}
        <label className="check">
          <input type="checkbox" checked={!!filters.open_only} onChange={(e) => set({ open_only: e.target.checked })} />
          Só abertos
        </label>
      </div>

      <ErrorNote error={tickets.error} />
      {tickets.isLoading ? (
        <Loading />
      ) : !shown.length ? (
        <Empty>Nenhum chamado com esses filtros.</Empty>
      ) : (
        <div className="table-wrap card">
          <table className="table clickable">
            <thead>
              <tr>
                <th>#</th>
                <th>Chamado</th>
                <th className="hide-sm">Fila</th>
                <th className="hide-sm">Prioridade</th>
                <th>Status</th>
                <th>Prazo</th>
                <th className="hide-sm">Responsável</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => (
                <tr key={t.id} onClick={() => navigate(`/chamados/${t.id}`)} tabIndex={0}
                    onKeyDown={(e) => e.key === 'Enter' && navigate(`/chamados/${t.id}`)}>
                  <td className="muted">{t.id}</td>
                  <td>
                    <strong>{t.title}</strong>
                    <div className="muted small">{t.customer.name}{t.reopen_count > 0 && ` · reaberto ${t.reopen_count}×`}<span className="show-sm"> · {t.category.name}</span></div>
                  </td>
                  <td className="hide-sm">{t.category.name}</td>
                  <td className="hide-sm"><PriorityBadge priority={t.priority} /></td>
                  <td><StatusBadge status={t.status} /></td>
                  <td><SlaBadge sla={t.sla} closed={t.status === 'fechado'} /></td>
                  <td className="hide-sm">{t.assignee?.name ?? <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {page && <Pager total={page.total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />}
    </>
  )
}
