import { expect, test } from '@playwright/test'
import { failOnConsoleErrors, loginAs, logout } from './helpers.ts'

const INTERNAL_NOTE = 'Cliente com 3 chamados de cobrança este mês.'

test('ciclo completo: cliente abre, atendente propõe, só o cliente encerra', async ({ page }) => {
  const noErrors = failOnConsoleErrors(page)

  await test.step('cliente abre um chamado e vê o prazo da fila', async () => {
    await loginAs(page, 'Cliente')
    await page.getByRole('link', { name: 'Abrir chamado' }).first().click()
    await page.getByLabel('Assunto').selectOption({ label: 'Cobrança' })
    await expect(page.getByText('Primeira resposta em até 4 h')).toBeVisible()
    await page.getByLabel('Título').fill('Cobrança em duplicidade no cartão')
    await page.getByLabel('Descreva o problema').fill('Fui cobrado duas vezes pela compra de 12/03 no cartão final 4321.')
    await page.getByRole('button', { name: 'Abrir chamado' }).click()
    await expect(page).toHaveURL(/\/chamados\/\d+$/)
    await expect(page.getByText('Aberto', { exact: true })).toBeVisible()
  })
  const ticketUrl = page.url()
  await logout(page)

  await test.step('atendente assume, anota internamente e propõe a solução', async () => {
    await loginAs(page, 'Atendente')
    await page.goto(ticketUrl)
    await page.getByRole('button', { name: 'Assumir chamado' }).click()
    await expect(page.getByText('assumiu o chamado')).toBeVisible()

    const composer = page.getByPlaceholder('Escreva para o cliente ou uma nota interna…')
    await composer.fill(INTERNAL_NOTE)
    await page.getByLabel('Nota interna (o cliente não vê)').check()
    await page.getByRole('button', { name: 'Enviar' }).click()
    await expect(page.getByText(INTERNAL_NOTE)).toBeVisible()
    await expect(page.getByText('No prazo').first()).toBeVisible() // an internal note is not a reply

    await composer.fill('Identificamos a duplicidade e fizemos o estorno. O valor volta na próxima fatura.')
    await page.getByRole('button', { name: 'Propor solução' }).click()
    await expect(page.getByText('Aguardando confirmação').first()).toBeVisible()
    await expect(page.getByText('Cumprido')).toHaveCount(2) // first response and resolution met
  })
  await logout(page)

  await test.step('cliente não vê a nota interna e confirma com nota 5', async () => {
    await loginAs(page, 'Cliente')
    await page.goto(ticketUrl)
    await expect(page.getByText('O seu problema foi resolvido?')).toBeVisible()
    await expect(page.getByText(INTERNAL_NOTE)).toHaveCount(0)
    await page.getByRole('button', { name: 'Sim, foi resolvido' }).click()
    await page.getByRole('radio', { name: '5 de 5' }).click()
    await page.getByRole('button', { name: 'Confirmar e encerrar' }).click()
    await expect(page.getByText('Solução confirmada pelo cliente')).toBeVisible()
    await expect(page.getByPlaceholder('Escreva uma mensagem para a equipe…')).toHaveCount(0) // closed: no more replies
  })

  noErrors()
})

test('cliente que rejeita a solução reabre o chamado', async ({ page }) => {
  await loginAs(page, 'Cliente')
  await page.getByRole('link', { name: 'Abrir chamado' }).first().click()
  await page.getByLabel('Assunto').selectOption({ label: 'Entrega' })
  await page.getByLabel('Título').fill('Pedido atrasado há uma semana')
  await page.getByLabel('Descreva o problema').fill('O rastreio não atualiza desde segunda-feira.')
  await page.getByRole('button', { name: 'Abrir chamado' }).click()
  await expect(page).toHaveURL(/\/chamados\/\d+$/)
  const ticketUrl = page.url()
  await logout(page)

  await loginAs(page, 'Atendente')
  await page.goto(ticketUrl)
  await page.getByPlaceholder('Escreva para o cliente ou uma nota interna…').fill('Reenviamos o pedido pela transportadora.')
  await page.getByRole('button', { name: 'Propor solução' }).click()
  await expect(page.getByText('Aguardando confirmação').first()).toBeVisible()
  await logout(page)

  await loginAs(page, 'Cliente')
  await page.goto(ticketUrl)
  await page.getByRole('button', { name: 'Não, continuo com o problema' }).click()
  await page.getByPlaceholder('Conte o que ainda não funciona…').fill('O rastreio continua parado.')
  await page.getByRole('button', { name: 'Reabrir chamado' }).click()
  await expect(page.getByText('Em atendimento', { exact: true })).toBeVisible()
  await expect(page.getByText('O rastreio continua parado.')).toBeVisible()
})

test('pedir informações pausa o prazo de resolução', async ({ page }) => {
  await loginAs(page, 'Atendente')
  await page.getByRole('checkbox', { name: 'Só abertos' }).check()
  await page.getByRole('combobox').filter({ hasText: 'Todos os status' }).selectOption('aberto')
  await page.locator('tbody tr').first().click()
  await page.getByRole('button', { name: 'Iniciar atendimento' }).click()
  await expect(page.getByText('Em atendimento', { exact: true })).toBeVisible()
  await page.getByPlaceholder('Escreva para o cliente ou uma nota interna…').fill('Pode enviar o número do pedido?')
  await page.getByRole('button', { name: 'Pedir informações' }).click()
  await expect(page.getByText('Aguardando cliente', { exact: true })).toBeVisible()
  await expect(page.getByText('parado enquanto aguarda o cliente')).toBeVisible()
})

test('perfis só acessam as próprias telas', async ({ page }) => {
  await loginAs(page, 'Cliente')
  await page.goto('/fila')
  await expect(page).toHaveURL(/\/chamados$/)
  await page.goto('/painel')
  await expect(page).toHaveURL(/\/chamados$/)
  await logout(page)

  await loginAs(page, 'Atendente')
  await page.goto('/painel')
  await expect(page).toHaveURL(/\/fila$/)
  await expect(page.getByRole('link', { name: 'Filas e SLA' })).toHaveCount(0)
})

test('sem login, qualquer rota leva à tela de entrada', async ({ page }) => {
  await page.goto('/fila')
  await expect(page).toHaveURL(/\/entrar$/)
})

test('gestor vê o painel com os indicadores do piloto', async ({ page }) => {
  await loginAs(page, 'Gestor')
  for (const label of ['Chamados abertos', 'Em risco', 'Vencidos', '1ª resposta no prazo', 'Solução confirmada', 'Reabertura']) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible() // tile (and table header)
  }
  await expect(page.getByRole('cell', { name: 'Cobrança' })).toBeVisible()
})

test('fila no celular não tem rolagem horizontal @mobile', async ({ page }) => {
  await loginAs(page, 'Atendente')
  await expect(page.locator('tbody tr').first()).toBeVisible()
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflows).toBe(false)
})

test('a fila é paginada no servidor', async ({ page }) => {
  await loginAs(page, 'Atendente')
  await page.getByRole('checkbox', { name: 'Só abertos' }).uncheck()   // demo data has more than one page in total
  const pager = page.getByRole('navigation', { name: 'Paginação' })
  await expect(pager.getByText(/^1–25 de \d+$/)).toBeVisible()
  const firstId = await page.locator('tbody tr td').first().textContent()
  await pager.getByRole('button', { name: 'Próxima →' }).click()
  await expect(pager.getByText(/^26–\d+ de \d+$/)).toBeVisible()
  await expect(page.locator('tbody tr td').first()).not.toHaveText(firstId!)
})
