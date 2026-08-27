import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API chạy ở container `api` khi trong docker, cổng 8010 khi chạy trên máy.
const target = process.env.VITE_API_TARGET || 'http://localhost:8010'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: { '/api': { target, changeOrigin: true } },
  },
})
