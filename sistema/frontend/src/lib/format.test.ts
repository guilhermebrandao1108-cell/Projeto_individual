import { describe, expect, it } from 'vitest'
import { describeEvent, duration, formatPercent, relative } from './format'

const NOW = new Date('2026-03-02T12:00:00Z')

describe('relative', () => {
  it.each([
    ['2026-03-02T12:30:00Z', 'em 30 min'],
    ['2026-03-02T15:00:00Z', 'em 3 h'],
    ['2026-03-02T09:00:00Z', 'há 3 h'],
    ['2026-03-06T12:00:00Z', 'em 4 dias'],
  ])('%s → %s', (iso, expected) => {
    expect(relative(iso, NOW)).toBe(expected)
  })
})

describe('duration', () => {
  it('picks a readable unit', () => {
    expect(duration(45 * 60)).toBe('45 min')
    expect(duration(60 * 3600)).toBe('3 dias')
    expect(duration(5 * 3600)).toBe('5 h')
  })
})

describe('formatPercent', () => {
  it('formats in pt-BR and shows a dash when there is no data', () => {
    expect(formatPercent(0.553)).toBe('55%')
    expect(formatPercent(null)).toBe('—')
  })
})

describe('describeEvent', () => {
  it('uses human labels for status changes', () => {
    expect(describeEvent('status', 'em_atendimento', 'resolvido')).toBe('mudou o status: Em atendimento → Aguardando confirmação')
  })
  it('distinguishes first assignment from transfer', () => {
    expect(describeEvent('atribuido', null, 'Lucas')).toBe('atribuiu a Lucas')
    expect(describeEvent('atribuido', 'Lucas', 'Marina')).toBe('transferiu de Lucas para Marina')
    expect(describeEvent('atribuido', null, 'Lucas', 'Lucas')).toBe('assumiu o chamado')
    expect(describeEvent('atribuido', 'Lucas', null)).toBe('devolveu o chamado à fila (Lucas foi desativado)')
  })
})
