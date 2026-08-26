import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    fs: {
      // The dashboard reads run artifacts straight off disk. No API server on the
      // critical path — a dead process cannot take the demo with it.
      allow: ['..'],
    },
  },
  optimizeDeps: {
    // duckdb-wasm ships its own workers; pre-bundling them breaks the worker URL resolution.
    exclude: ['@duckdb/duckdb-wasm'],
  },
  worker: { format: 'es' },
  build: {
    target: 'es2022',
    rollupOptions: {
      output: {
        manualChunks: {
          duckdb: ['@duckdb/duckdb-wasm'],
          plot: ['@observablehq/plot'],
        },
      },
    },
  },
})
