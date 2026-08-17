import { defineConfig, devices } from '@playwright/test'

// E2E contra el sistema real (frontend + backend + worker en Docker), sin
// mocks. No arrancamos el dev server desde acá: el frontend puede estar
// corriendo ya en :5173, o se levanta a mano con `pnpm dev` antes de correr
// los tests (.claude/rules/testing.md).
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
