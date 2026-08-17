// Script standalone (no es un *.spec.ts, así que `pnpm test:e2e` / `playwright
// test` no lo levanta) para capturar las 4 pantallas reales que usa el
// README. Corre contra el sistema real (frontend :5173 + backend :8000), sin
// mocks, con la cuenta de prueba ya poblada. Ejecutar con:
//   node e2e/screenshots.mjs
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = resolve(__dirname, '../../docs/screenshots')
mkdirSync(OUT_DIR, { recursive: true })

const BASE_URL = 'http://localhost:5173'
const EMAIL = 'fase2test@example.com'
// Password de la cuenta de prueba local (Docker dev, sin valor fuera de
// localhost) - se lee de env para no dejar el literal en el código fuente.
const PASSWORD = process.env.E2E_TEST_PASSWORD || 'correcthorsebattery'
const DATASET_NAME = 'Mini Test'

async function main() {
  const browser = await chromium.launch()
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })
  const page = await context.newPage()

  // 1) Login sin loguear. TerminalIntro tipea el heading con un efecto
  // typewriter de ~3.5s (frontend/src/features/auth/TerminalIntro.tsx) -
  // esperamos a que termine para no capturar el texto a medio tipear.
  await page.goto(`${BASE_URL}/login`)
  await page.getByLabel('Email').waitFor({ state: 'visible' })
  await page.waitForTimeout(4000)
  await page.screenshot({ path: resolve(OUT_DIR, 'login.png') })
  console.log('captured login.png')

  // Login real (una sola vez - el rate limit de /api/auth/login es 5/minute).
  await page.getByLabel('Email').fill(EMAIL)
  await page.getByLabel('Contraseña').and(page.getByRole('textbox')).fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await page.waitForURL(/\/datasets$/, { timeout: 15000 })

  // 2) /datasets con la grilla real visible.
  await page.getByRole('heading', { name: 'Datasets' }).waitFor({ state: 'visible' })
  await page.getByRole('button', { name: new RegExp(DATASET_NAME) }).waitFor({ state: 'visible', timeout: 15000 })
  await page.waitForTimeout(300) // asentar animaciones/hover residual
  await page.screenshot({ path: resolve(OUT_DIR, 'datasets.png') })
  console.log('captured datasets.png')

  // 3) /analisis con un chat REAL ya respondido - "Ventas Gigante CSV" ya
  // tiene un hilo con varias preguntas/respuestas de sesiones anteriores
  // (agregacion SUM por producto, listado sin agrupar), mucho mas
  // representativo del riel de traza que una pregunta trivial nueva
  // ("¿cuántas filas tiene?" repetida) - no dispara ningun analisis nuevo,
  // solo selecciona el dataset y espera a que el hilo existente cargue.
  await page.goto(`${BASE_URL}/analisis`)
  await page.getByRole('heading', { name: 'Análisis' }).waitFor({ state: 'visible' })
  const datasetSelect = page.getByLabel('Dataset activo')
  await datasetSelect.waitFor({ state: 'visible', timeout: 15000 })
  await datasetSelect.selectOption({ label: 'Ventas Gigante CSV' })
  await page.getByText('Respuesta', { exact: true }).first().waitFor({ state: 'visible', timeout: 15000 })
  await page.mouse.move(0, 0)
  await page.waitForTimeout(300)
  await page.screenshot({ path: resolve(OUT_DIR, 'analisis.png') })
  console.log('captured analisis.png')

  // 4) /documentos con al menos un documento en estado "Listo".
  await page.goto(`${BASE_URL}/documentos`)
  await page.getByRole('heading', { name: 'Documentos' }).waitFor({ state: 'visible' })
  await page.getByText('Listo').first().waitFor({ state: 'visible', timeout: 15000 })
  await page.waitForTimeout(300)
  await page.screenshot({ path: resolve(OUT_DIR, 'documentos.png') })
  console.log('captured documentos.png')

  await browser.close()
  console.log('done')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
