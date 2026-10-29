import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  const backendOrigin = env.VITE_DJANGO_ORIGIN || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    resolve: {
      dedupe: ['react', 'react-dom'],
    },
    server: {
      proxy: {
        '/api': {
          target: backendOrigin,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyRequest, request) => {
              if (request.headers.origin) {
                proxyRequest.setHeader('origin', backendOrigin)
              }
            })
          },
        },
      },
    },
  }
})
