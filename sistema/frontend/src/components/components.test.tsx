import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { Sla } from '../api/types'
import { SlaBadge } from './Badges'
import { Pager, Rating } from './ui'

const sla = (over: Partial<Sla>): Sla => ({
  first_response: 'no_prazo',
  first_response_due_at: '2099-01-01T00:00:00Z',
  resolution: 'no_prazo',
  resolution_due_at: '2099-01-02T00:00:00Z',
  ...over,
})

describe('SlaBadge', () => {
  it('shows the first-response target while it is pending', () => {
    render(<SlaBadge sla={sla({ first_response: 'em_risco' })} />)
    expect(screen.getByText(/1ª resposta · Em risco/)).toBeInTheDocument()
  })

  it('switches to the resolution target once the first reply is met', () => {
    render(<SlaBadge sla={sla({ first_response: 'cumprido', resolution: 'vencido', resolution_due_at: '2000-01-01T00:00:00Z' })} />)
    expect(screen.getByText(/Resolução · Vencido/)).toBeInTheDocument()
    expect(screen.getByText(/venceu há/)).toBeInTheDocument()
  })

  it('shows a paused clock without a countdown', () => {
    render(<SlaBadge sla={sla({ first_response: 'cumprido', resolution: 'pausado' })} />)
    expect(screen.getByText(/Resolução · Pausado/)).toBeInTheDocument()
    expect(screen.getByText(/aguardando o cliente/)).toBeInTheDocument()
    expect(screen.queryByText(/vence/)).not.toBeInTheDocument()
  })

  it('hides the countdown on closed tickets', () => {
    render(<SlaBadge sla={sla({ first_response: 'cumprido', resolution: 'cumprido' })} closed />)
    expect(screen.queryByText(/vence/)).not.toBeInTheDocument()
  })
})

function RatingHarness() {
  const [value, setValue] = useState<number | null>(null)
  return (
    <>
      <Rating value={value} onChange={setValue} />
      <output>{value ?? 'sem nota'}</output>
    </>
  )
}

describe('Rating', () => {
  it('selects and clears a rating', async () => {
    render(<RatingHarness />)
    await userEvent.click(screen.getByRole('radio', { name: '4 de 5' }))
    expect(screen.getByText('4')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('radio', { name: '4 de 5' }))
    expect(screen.getByText('sem nota')).toBeInTheDocument()
  })
})

describe('Pager', () => {
  it('shows the range and moves by one page', async () => {
    const calls: number[] = []
    render(<Pager total={53} limit={25} offset={25} onChange={(o) => calls.push(o)} />)
    expect(screen.getByText('26–50 de 53')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Próxima →' }))
    await userEvent.click(screen.getByRole('button', { name: '← Anterior' }))
    expect(calls).toEqual([50, 0])
  })

  it('is hidden when everything fits in one page', () => {
    const { container } = render(<Pager total={10} limit={25} offset={0} onChange={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
