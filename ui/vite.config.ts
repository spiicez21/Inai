import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, type Plugin } from 'vite'

const RUNS_DIR = path.resolve(import.meta.dirname, '../runs')

/**
 * Serve `../runs` at `/runs` during development.
 *
 * The dashboard reads run artifacts (scorecard.json, exceptions.parquet) straight off disk.
 * They live outside the UI root because they are produced by the Python pipeline and are
 * regenerable from a seed — they are not UI assets and must not be copied into `public/`.
 * For a static deploy, copy `runs/<id>/` next to the built bundle instead.
 */
function serveRuns(): Plugin {
  return {
    name: 'inai-serve-runs',
    configureServer(server) {
      server.middlewares.use('/runs', (req, res, next) => {
        const rel = decodeURIComponent((req.url ?? '/').split('?')[0])
        const file = path.join(RUNS_DIR, rel)
        // Containment check — a path escaping the runs directory is never served.
        if (!file.startsWith(RUNS_DIR) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
          return next()
        }
        const type = file.endsWith('.json')
          ? 'application/json'
          : file.endsWith('.parquet')
            ? 'application/vnd.apache.parquet'
            : file.endsWith('.csv')
              ? 'text/csv'
              : 'application/octet-stream'
        res.setHeader('Content-Type', type)
        fs.createReadStream(file).pipe(res)
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), serveRuns()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
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
        // Rolldown's chunking API (Vite 8). DuckDB-Wasm and Plot are the two heavy deps;
        // splitting them keeps the dashboard shell interactive while they stream in.
        codeSplitting: {
          groups: [
            { name: 'duckdb', test: /@duckdb[\\/]/ },
            { name: 'plot', test: /@observablehq[\\/]/ },
          ],
        },
      },
    },
  },
})
