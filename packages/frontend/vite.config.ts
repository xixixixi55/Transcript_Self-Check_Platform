import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@biji/shared': path.resolve(__dirname, '../shared'),
    },
  },
  server: {
    port: 30000,
    proxy: {
      '/api': {
        target: 'http://localhost:30010',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
