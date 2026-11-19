import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': {
          target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
          timeout: 300000,
          proxyTimeout: 300000,
          configure(proxy) {
            proxy.on('proxyRes', (proxyRes, req) => {
              if (String(req.url || '').includes('/chat/stream')) {
                proxyRes.headers['cache-control'] = 'no-cache, no-store'
                proxyRes.headers['x-accel-buffering'] = 'no'
                delete proxyRes.headers['content-length']
              }
            })
          },
        },
      },
    },
  }
})
