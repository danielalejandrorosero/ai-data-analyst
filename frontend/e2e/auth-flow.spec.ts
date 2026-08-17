import { expect, test } from '@playwright/test'

// Spec chico y determinista: registro de una cuenta nueva + login/logout,
// sin tocar datasets/análisis (eso lo cubre main-flow.spec.ts). Corre
// contra el backend real.
test('registro de cuenta nueva -> redirige a /datasets -> logout -> vuelve a /login', async ({ page }) => {
  const unique = `${Date.now()}-${Math.floor(Math.random() * 100000)}`
  const email = `e2e-${unique}@example.com`
  // Cuenta descartable creada por este mismo test - password generada en
  // runtime, no hay ningun literal que valga la pena hardcodear.
  const password = `Pw${unique}!`
  const orgName = `E2E Org ${unique}`

  await page.goto('/register')

  await page.getByLabel('Nombre de la organización').fill(orgName)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Contraseña').and(page.getByRole('textbox')).fill(password)
  await page.getByRole('button', { name: 'Crear cuenta' }).click()

  await expect(page).toHaveURL(/\/datasets$/, { timeout: 15000 })
  await expect(page.getByRole('heading', { name: 'Datasets' })).toBeVisible()

  // Logout desde el AppShell (botón con el nombre de la organización).
  await page.getByRole('button', { name: new RegExp(orgName) }).click()
  await expect(page).toHaveURL(/\/login$/, { timeout: 15000 })

  // Login de vuelta con la misma cuenta recién creada.
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Contraseña').and(page.getByRole('textbox')).fill(password)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()

  await expect(page).toHaveURL(/\/datasets$/, { timeout: 15000 })
  await expect(page.getByRole('heading', { name: 'Datasets' })).toBeVisible()
})
