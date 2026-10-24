import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // VITE_BACKEND_URL turns on real requests; /api is proxied there so the backend needs no CORS setup.
  const { VITE_BACKEND_URL } = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react(), tailwindcss()],
    server: VITE_BACKEND_URL ? { proxy: { '/api': VITE_BACKEND_URL } } : undefined,
  }
})
