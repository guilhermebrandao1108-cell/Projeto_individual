import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// In development the browser calls /api/* and Vite forwards it to FastAPI,
// so the frontend never hard-codes the backend URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.API_URL ?? 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'], // e2e/ belongs to Playwright
    setupFiles: ['./src/test/setup.ts'],
  },
})
