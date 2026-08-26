import { cn } from '@/lib/cn'
import { EXCEPTION_LABEL, fmtCount, fmtPaiseCompact, fmtPct, TIER_SHORT } from '@/lib/format'
import { queryExceptions, type ExceptionFilter } from '@/lib/runs'
import type { ExceptionBucket, ExceptionRow, MatchTierId } from '@/types/scorecard'
import { Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ExceptionTable } from './ExceptionTable'
import { Card, PanelHeader } from './primitives'

const TIERS: MatchTierId[] = [
  't0_exact',
  't1_deterministic',
  't2_fuzzy',
  't3_structural',
  't4_adversarial',
]

/**
 * The exception list, displayed by default and never behind a toggle (§9.6).
 *
 * Filtering runs as SQL in DuckDB-Wasm rather than as JS array work, so it stays instant at
 * 25,000 rows and the same code path serves smoke and stress.
 */
export function ExceptionsPanel({
  buckets,
  totalRecords,
  exceptionRatePct,
  onSelect,
  selectedId,
}: {
  buckets: ExceptionBucket[]
  totalRecords: number
  exceptionRatePct: number
  onSelect: (row: ExceptionRow) => void
  selectedId?: string | null
}) {
  const [filter, setFilter] = useState<ExceptionFilter>({})
  const [search, setSearch] = useState('')
  const [rows, setRows] = useState<ExceptionRow[]>([])
  const [total, setTotal] = useState(0)

  // Debounced so typing does not fire a query per keystroke.
  useEffect(() => {
    const id = setTimeout(() => setFilter((f) => ({ ...f, search: search || null })), 180)
    return () => clearTimeout(id)
  }, [search])

  useEffect(() => {
    let cancelled = false
    queryExceptions(filter).then((r) => {
      if (cancelled) return
      setRows(r)
      if (!filter.cls && !filter.tier && !filter.search) setTotal(r.length)
    })
    return () => {
      cancelled = true
    }
  }, [filter])

  const active = filter.cls || filter.tier || filter.search

  return (
    <Card className="flex min-h-0 flex-col">
      <PanelHeader
        title="Every record we could not resolve, and why"
        note={
          <>
            Target 5–12% of the batch. A submission reporting zero exceptions is either lying or
            not trying. Currently{' '}
            <span className="num text-exception">{fmtPct(exceptionRatePct)}</span> of{' '}
            <span className="num">{fmtCount(totalRecords)}</span>.
          </>
        }
        right={
          <div className="relative">
            <Search
              size={13}
              className="text-base-600 pointer-events-none absolute top-1/2 left-2 -translate-y-1/2"
            />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="id, ledger, UTR…"
              className="bg-base-950 border-base-800 text-base-200 placeholder:text-base-600 focus:border-accent/50 w-52 rounded border py-1 pr-2 pl-7 font-mono text-[0.6875rem] outline-none"
            />
          </div>
        }
      />

      {/* Class chips, ordered by count. Amount rides along because the biggest class by
          count is rarely the biggest by rupees, and both matter. */}
      <div className="hairline flex flex-wrap gap-1.5 px-4 py-2.5">
        {buckets.map((b) => {
          const on = filter.cls === b.cls
          return (
            <button
              key={b.cls}
              onClick={() => setFilter((f) => ({ ...f, cls: on ? null : b.cls }))}
              className={cn(
                'flex items-center gap-1.5 rounded px-2 py-1 text-[0.6875rem] ring-1 ring-inset transition-colors',
                on
                  ? 'bg-accent/15 text-accent ring-accent/35'
                  : 'bg-base-850/60 text-base-400 ring-base-800 hover:bg-base-850 hover:text-base-200',
              )}
              title={`${fmtPaiseCompact(b.amount_paise)} · ${fmtPct(b.pct_of_batch)} of batch`}
            >
              <span>{EXCEPTION_LABEL[b.cls] ?? b.cls}</span>
              <span className="num opacity-60">{fmtCount(b.count)}</span>
            </button>
          )
        })}
      </div>

      <div className="hairline flex items-center gap-1.5 px-4 py-2">
        <span className="text-base-600 mr-1 text-[0.6875rem]">Tier</span>
        {TIERS.map((t) => {
          const on = filter.tier === t
          return (
            <button
              key={t}
              onClick={() => setFilter((f) => ({ ...f, tier: on ? null : t }))}
              className={cn(
                'rounded px-2 py-0.5 font-mono text-[0.6875rem] ring-1 ring-inset transition-colors',
                on
                  ? 'bg-accent/15 text-accent ring-accent/35'
                  : 'bg-base-850/60 text-base-500 ring-base-800 hover:text-base-200',
              )}
            >
              {TIER_SHORT[t]}
            </button>
          )
        })}
        {active ? (
          <button
            onClick={() => {
              setFilter({})
              setSearch('')
            }}
            className="text-base-500 hover:text-base-200 ml-auto flex items-center gap-1 text-[0.6875rem]"
          >
            <X size={11} /> clear
          </button>
        ) : null}
      </div>

      <div className="hairline min-h-0 flex-1">
        <ExceptionTable
          rows={rows}
          totalCount={total || rows.length}
          onSelect={onSelect}
          selectedId={selectedId}
        />
      </div>
    </Card>
  )
}
