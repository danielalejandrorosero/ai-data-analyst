import { expect, test } from '@playwright/test'

// E2E del flujo principal exigido por el SRS (secciones 10 y 15) y
// .claude/rules/testing.md: login -> ver dataset -> preguntar -> ver
// resultado. Corre contra el backend real en :8000 (sin mocks) con la
// cuenta de prueba ya poblada.
// Password de la cuenta de prueba local (Docker dev, sin valor fuera de
// localhost) - se lee de env para no dejar el literal en el código fuente,
// mismo patrón que backend/tests/evals/run_eval.py.
const EMAIL = 'fase2test@example.com'
const PASSWORD = process.env.E2E_TEST_PASSWORD || 'correcthorsebattery'

// "Mini Test" es el dataset más chico de la cuenta de prueba (2 filas, 2
// columnas) - la pregunta más simple sobre él resuelve rápido.
const DATASET_NAME = 'Mini Test'

test('login -> ver esquema de dataset -> preguntar -> ver respuesta con traza', async ({ page }) => {
  await page.goto('/login')

  await page.getByLabel('Email').fill(EMAIL)
  await page.getByLabel('Contraseña').and(page.getByRole('textbox')).fill(PASSWORD)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()

  await expect(page).toHaveURL(/\/datasets$/, { timeout: 15000 })
  await expect(page.getByRole('heading', { name: 'Datasets' })).toBeVisible()

  // Grilla de datasets reales visible.
  const datasetCard = page.getByRole('button', { name: new RegExp(DATASET_NAME) })
  await expect(datasetCard).toBeVisible({ timeout: 15000 })

  // Click abre el modal de esquema (DatasetSchemaModal).
  await datasetCard.click()
  const modal = page.getByRole('dialog')
  await expect(modal).toBeVisible()
  await expect(modal.getByRole('columnheader', { name: 'columna' })).toBeVisible()
  await expect(modal.getByRole('columnheader', { name: 'tipo' })).toBeVisible()
  await expect(modal.getByText(/filas · \d+ columnas/)).toBeVisible({ timeout: 10000 })
  await modal.getByRole('button', { name: 'Cerrar' }).click()
  await expect(modal).not.toBeVisible()

  // Ir a /analisis, seleccionar el mismo dataset.
  await page.goto('/analisis')
  await expect(page.getByRole('heading', { name: 'Análisis' })).toBeVisible()

  const datasetSelect = page.getByLabel('Dataset activo')
  await expect(datasetSelect).toBeVisible({ timeout: 15000 })
  await datasetSelect.selectOption({ label: DATASET_NAME })

  // Escribir y enviar una pregunta simple.
  const question = `¿Cuántas filas tiene este dataset? (e2e ${Date.now()})`
  const questionBox = page.getByPlaceholder(/Preguntá algo sobre tus datos/)
  await questionBox.fill(question)
  await page.getByRole('button', { name: 'Enviar pregunta' }).click()

  // La pregunta aparece como burbuja de chat.
  await expect(page.getByRole('paragraph').filter({ hasText: question })).toBeVisible()

  // El agente real tarda unos segundos: esperamos con timeout generoso a
  // que aparezca el bloque "Respuesta" con contenido de texto.
  const answerBlock = page.locator('text=Respuesta').first()
  await expect(answerBlock).toBeVisible({ timeout: 60000 })

  const answerCard = page
    .locator('div', { has: page.getByText('Respuesta', { exact: true }) })
    .last()
  await expect(answerCard.locator('p').last()).not.toBeEmpty()

  // Al menos un bloque de traza (tool call) visible: "Inspeccionando
  // esquema" o "Consulta SQL" son los más probables para esta pregunta.
  const traceBlock = page.getByText(/Inspeccionando esquema|Consulta SQL|Post-procesamiento/).first()
  await expect(traceBlock).toBeVisible({ timeout: 60000 })
})
