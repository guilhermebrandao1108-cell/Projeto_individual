import type { ReactNode } from 'react'
import { ApiError } from '../api/client'

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null
  const message = error instanceof ApiError ? error.message : 'Não foi possível falar com o servidor.'
  return (
    <p className="error" role="alert">
      {message}
    </p>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>
}

/** "1–25 de 213" with previous/next buttons; hidden when everything fits in one page. */
export function Pager({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null
  const last = Math.min(offset + limit, total)
  return (
    <nav className="pager" aria-label="Paginação">
      <button className="btn small" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        ← Anterior
      </button>
      <span className="muted small">
        {offset + 1}–{last} de {total}
      </span>
      <button className="btn small" disabled={last >= total} onClick={() => onChange(offset + limit)}>
        Próxima →
      </button>
    </nav>
  )
}

export function Loading() {
  return <p className="muted">Carregando…</p>
}

/** 1–5 star picker; clicking the selected star clears it (rating is optional). */
export function Rating({ value, onChange }: { value: number | null; onChange: (v: number | null) => void }) {
  return (
    <div className="rating" role="radiogroup" aria-label="Nota do atendimento">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} de 5`}
          className={value !== null && n <= value ? 'star on' : 'star'}
          onClick={() => onChange(value === n ? null : n)}
        >
          ★
        </button>
      ))}
    </div>
  )
}
