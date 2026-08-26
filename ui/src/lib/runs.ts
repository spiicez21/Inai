/**
 * Loading a run. Artifacts-first: everything the dashboard shows comes from
 * `runs/{run_id}/`, read over plain HTTP. No API, no server state.
 */

import type { ExceptionRow, Scorecard } from '@/types/scorecard'
import { query, registerParquet } from './duckdb'

/** Vite serves the repo root via `server.fs.allow`; in prod these are copied next to the bundle. */
const RUNS_BASE = import.meta.env.VITE_RUNS_BASE ?? '/runs'

export function runUrl(runId: string, file: string): string {
  return `${RUNS_BASE}/${runId}/${file}`
}

/** `runs/latest.json` is what the dashboard opens when no run_id is in the URL. */
export async function fetchLatestRunId(): Promise<string> {
  const res = await fetch(`${RUNS_BASE}/latest.json`)
  if (!res.ok) throw new Error(`No runs found. Run: uv run inai run --config configs/demo.yaml`)
  const { run_id } = (await res.json()) as { run_id: string }
  return run_id
}

export async function fetchScorecard(runId: string): Promise<Scorecard> {
  const res = await fetch(runUrl(runId, 'scorecard.json'))
  if (!res.ok) throw new Error(`scorecard.json missing for run ${runId}`)
  return (await res.json()) as Scorecard
}

/**
 * Load the exception list into DuckDB. Registered once per run, then queried repeatedly —
 * filtering, faceting and sorting all happen in SQL rather than in React.
 */
export async function loadExceptions(runId: string): Promise<void> {
  const file = `exceptions_${runId}.parquet`
  await registerParquet(file, runUrl(runId, 'exceptions.parquet'))
  await query(`CREATE OR REPLACE VIEW exceptions AS SELECT * FROM read_parquet('${file}')`)
}

export interface ExceptionFilter {
  cls?: string | null
  tier?: string | null
  search?: string | null
}

function whereClause(f: ExceptionFilter): string {
  const parts: string[] = []
  if (f.cls) parts.push(`cls = ${lit(f.cls)}`)
  if (f.tier) parts.push(`tier = ${lit(f.tier)}`)
  if (f.search) {
    const q = lit(`%${f.search.toLowerCase()}%`)
    parts.push(
      `(lower(exception_id) LIKE ${q} OR lower(ledger_ref) LIKE ${q} ` +
        `OR lower(settlement_ref) LIKE ${q} OR lower(bank_ref) LIKE ${q} ` +
        `OR lower(machine_reason) LIKE ${q})`,
    )
  }
  return parts.length ? `WHERE ${parts.join(' AND ')}` : ''
}

/** Single-quote escaping. These values come from our own URL state, never from a third party,
 *  but a reconciler that concatenates unescaped SQL is not a reconciler anyone should trust. */
function lit(v: string): string {
  return `'${v.replaceAll("'", "''")}'`
}

export async function queryExceptions(f: ExceptionFilter, limit = 50_000): Promise<ExceptionRow[]> {
  return query<ExceptionRow>(
    `SELECT exception_id, cls, tier, ledger_ref, settlement_ref, bank_ref,
            amount_paise, machine_reason, human_reason, routed_action
     FROM exceptions ${whereClause(f)}
     ORDER BY amount_paise DESC
     LIMIT ${limit}`,
  )
}

export async function countExceptions(f: ExceptionFilter): Promise<number> {
  const rows = await query<{ n: number }>(
    `SELECT count(*)::BIGINT AS n FROM exceptions ${whereClause(f)}`,
  )
  return rows[0]?.n ?? 0
}

export interface ClassTierCell {
  cls: string
  tier: string
  n: number
  amount_paise: number
}

/** Exception class × difficulty tier. The cross-tab is where the interesting structure is:
 *  UNAPPLIED_CASH concentrating in T2/T3 is the whole false-dunning story in one grid. */
export async function queryClassByTier(): Promise<ClassTierCell[]> {
  return query<ClassTierCell>(
    `SELECT cls, tier, count(*)::BIGINT AS n, sum(amount_paise)::BIGINT AS amount_paise
     FROM exceptions GROUP BY cls, tier ORDER BY cls, tier`,
  )
}
