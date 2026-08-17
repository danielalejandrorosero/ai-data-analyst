/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // e2e/ son specs de Playwright (otro test runner, corren con
    // `pnpm test:e2e`) - sin esto Vitest los levanta tambien y explota
    // porque Playwright Test no permite llamar a su propio `test()` fuera
    // de su runner.
    exclude: ['**/node_modules/**', '**/e2e/**'],
  },
})
