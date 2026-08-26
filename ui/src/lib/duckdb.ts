/**
 * DuckDB-Wasm — SQL over the run's Parquet artifacts, in the browser.
 *
 * This is why there is no API server on the critical path. `stress.yaml` is 25,000 records;
 * DuckDB reads that Parquet and answers a GROUP BY in single-digit milliseconds, entirely
 * client-side. The dashboard is a static bundle plus a directory of run artifacts, so it
 * deploys anywhere and cannot be taken down mid-demo by a dead process.
 *
 * It is also on-thesis: the same engine that stores the run backs the dashboard reading it.
 */

import * as duckdb from '@duckdb/duckdb-wasm'

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null

async function init(): Promise<duckdb.AsyncDuckDB> {
  const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles())
  // Worker is created from a blob so no separate worker file has to be served.
  const workerUrl = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' }),
  )
  const worker = new Worker(workerUrl)
  const logger = new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING)
  const db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)
  URL.revokeObjectURL(workerUrl)
  return db
}

export function getDB(): Promise<duckdb.AsyncDuckDB> {
  dbPromise ??= init()
  return dbPromise
}

/** Register a run's Parquet file under a stable name, then query it as a table. */
export async function registerParquet(name: string, url: string): Promise<void> {
  const db = await getDB()
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`)
  await db.registerFileBuffer(name, new Uint8Array(await res.arrayBuffer()))
}

/** Run a query and get plain JS objects back. BigInt is normalised to number. */
export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  const db = await getDB()
  const conn = await db.connect()
  try {
    const result = await conn.query(sql)
    return result.toArray().map((row) => normalise(row.toJSON())) as T[]
  } finally {
    await conn.close()
  }
}

/**
 * Arrow returns 64-bit integers as BigInt. Every monetary value in INAI is int64 paise, so
 * this path is hot — and `JSON.stringify` throws on BigInt, which would break silently at
 * the first render rather than here.
 *
 * Paise fit in a double well past any plausible batch (2^53 paise is ~₹90 lakh crore), so
 * the conversion is lossless in practice. It is still a conversion, so it happens in exactly
 * one place.
 */
function normalise(row: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(row)) {
    out[k] = typeof v === 'bigint' ? Number(v) : v
  }
  return out
}
