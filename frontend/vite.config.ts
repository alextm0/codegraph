import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8474',
      '/ws': { target: 'ws://localhost:8474', ws: true },
    },
  },
  build: {
    outDir: '../src/codegraph/visualizer/static/dist',
    emptyOutDir: true,
  },
})
