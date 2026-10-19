import { expect, type Page } from '@playwright/test'

export type Profile = 'Cliente' | 'Atendente' | 'Gestor'

/** Logs in with the demo shortcut buttons (available in the dev server only). */
export async function loginAs(page: Page, profile: Profile) {
  await page.goto('/entrar')
  await page.getByRole('button', { name: profile, exact: true }).click()
  const heading = { Cliente: 'Meus chamados', Atendente: 'Fila de atendimento', Gestor: 'Painel' }[profile]
  await expect(page.getByRole('heading', { name: heading })).toBeVisible()
}

export async function logout(page: Page) {
  await page.getByRole('button', { name: 'Sair' }).click()
  await expect(page).toHaveURL(/\/entrar$/)
}

/** Fails the test on any uncaught error or console error during the flow. */
export function failOnConsoleErrors(page: Page) {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  return () => expect(errors, errors.join('\n')).toEqual([])
}
