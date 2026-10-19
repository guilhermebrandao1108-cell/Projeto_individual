import { formatNumber } from './format'

export type Delta = { text: string; good: boolean | null }

/** Change against the previous period of the same length. Rates in percentage points. */
export function compare(current: number | null, previous: number | null, kind: 'rate' | 'hours' | 'score',
                        higherIsBetter: boolean): Delta | null {
  if (current === null || previous === null) return null
  const diff = kind === 'rate' ? (current - previous) * 100 : current - previous
  if (Math.abs(diff) < 0.05) return { text: 'igual ao período anterior', good: null }
  const unit = kind === 'rate' ? ' pp' : kind === 'hours' ? ' h' : ''
  return { text: `${diff > 0 ? '▲' : '▼'} ${formatNumber(Math.abs(diff))}${unit} vs período anterior`, good: diff > 0 === higherIsBetter }
}
