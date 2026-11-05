import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: loadEnv(mode, process.cwd(), '').API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure(proxy) {
          proxy.on('error', (_error, _request, response) => {
            if ('writeHead' in response && !response.headersSent) {
              response.writeHead(503, { 'Content-Type': 'application/json' })
              response.end(JSON.stringify({ detail: 'Backend connection failed. Start Django with python manage.py runserver (port 8000), or check API_PROXY_TARGET in the frontend configuration.' }))
            }
          })
        },
      },
    },
  },
}))
