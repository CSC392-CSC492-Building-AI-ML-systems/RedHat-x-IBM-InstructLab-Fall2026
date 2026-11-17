import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { target: 'es2022', chunkSizeWarningLimit: 5000, assetsInlineLimit: 0 },
  worker: { format: 'es' },
  // `npm run dev` proxies API calls to a local `npm run dev:server`
  server: { proxy: { '/api': { target: 'http://localhost:8080', changeOrigin: false } } },
})
