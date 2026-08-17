import { expect, test } from '@playwright/test'

// RNF-030: "no existen elementos críticos fuera de viewport en resoluciones
// soportadas" (desktop y tablet, no celular). Este spec cubre el rango
// tablet (768px-1024px) sobre las dos pantallas centrales del flujo
// principal: /datasets y /analisis (AppShell + chat de análisis).
// Misma cuenta de prueba que main-flow.spec.ts.
const EMAIL = 'fase2test@example.com'
const PASSWORD = process.env.E2E_TEST_PASSWORD || 'correcthorsebattery'

const TABLET_VIEWPORTS = [
  { name: 'iPad portrait', width: 768, height: 1024 },
  { name: 'iPad landscape / tablet ancho', width: 1024, height: 768 },
]

async function expectNoHorizontalOverflow(page: import('@playwright/test').Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth)
}

for (const viewport of TABLET_VIEWPORTS) {
  test(`sin scroll horizontal en /datasets y /analisis a ${viewport.name} (${viewport.width}x${viewport.height})`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height })

    await page.goto('/login')
    await page.getByLabel('Email').fill(EMAIL)
    await page.getByLabel('Contraseña').and(page.getByRole('textbox')).fill(PASSWORD)
    await page.getByRole('button', { name: 'Entrar', exact: true }).click()
    await expect(page).toHaveURL(/\/datasets$/, { timeout: 15000 })
    await expect(page.getByRole('heading', { name: 'Datasets' })).toBeVisible()

    await expectNoHorizontalOverflow(page)

    await page.goto('/analisis')
    await expect(page.getByRole('heading', { name: 'Análisis' })).toBeVisible()

    // El selector de dataset activo aparece una vez que cargan los
    // datasets - esperamos a que el layout de dos columnas (chats +
    // conversación) esté montado antes de medir overflow.
    const datasetSelect = page.getByLabel('Dataset activo')
    await expect(datasetSelect).toBeVisible({ timeout: 15000 })

    await expectNoHorizontalOverflow(page)
  })
}
