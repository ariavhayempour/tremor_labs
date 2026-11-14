import { defineConfig } from '@playwright/test'
export default defineConfig({ testDir: './e2e', use: { baseURL: 'http://localhost:5174' }, webServer: { command: 'npm run dev -- --host localhost --port 5174', url: 'http://localhost:5174', reuseExistingServer: !process.env.CI, env: { VITE_USE_FIXTURES: '1' } } })
