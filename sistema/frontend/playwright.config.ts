import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run the real stack: a freshly seeded FastAPI backend and the Vite dev server,
// on their own ports so they never touch the development database or servers.
const API_PORT = 8001
const WEB_PORT = 5174
const isWindows = process.platform === 'win32'
const python = process.env.PYTHON ?? (isWindows ? '.venv\\Scripts\\python.exe' : 'python')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // the flows share one seeded database
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    locale: 'pt-BR',
    trace: 'retain-on-failure',
    // Locally on Windows use the installed Edge; elsewhere (and in CI) Playwright's Chromium.
    channel: process.env.PW_CHANNEL ?? (isWindows && !process.env.CI ? 'msedge' : undefined),
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1360, height: 900 } }, grepInvert: /@mobile/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
  webServer: [
    {
      command: `${python} -m app.seed --reset && ${python} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://localhost:${API_PORT}/health`,
      env: { DATABASE_URL: 'sqlite:///./e2e.db', SECRET_KEY: 'e2e-only-secret-key-with-at-least-32-bytes' },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npm run dev -- --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
