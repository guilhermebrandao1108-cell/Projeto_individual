import { describe, expect, it } from 'vitest'
import { compare } from './compare'

describe('compare', () => {
  it('reports rate changes in percentage points', () => {
    expect(compare(0.62, 0.55, 'rate', true)).toEqual({ text: '▲ 7 pp vs período anterior', good: true })
  })
  it('knows when lower is better', () => {
    expect(compare(8.5, 10, 'hours', false)).toEqual({ text: '▼ 1,5 h vs período anterior', good: true })
    expect(compare(0.2, 0.1, 'rate', false)?.good).toBe(false)
  })
  it('treats tiny differences as no change and missing data as unknown', () => {
    expect(compare(4.01, 4.0, 'score', true)).toEqual({ text: 'igual ao período anterior', good: null })
    expect(compare(null, 0.5, 'rate', true)).toBeNull()
  })
})
