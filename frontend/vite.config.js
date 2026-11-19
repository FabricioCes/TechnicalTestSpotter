import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the React app calls /api, which Vite forwards to Django.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
