import { EXCEPTION_LABEL, fmtCount, fmtPaiseCompact, fmtPct } from '@/lib/format'
import { queryExceptions, type ExceptionFilter } from '@/lib/runs'
import type { ExceptionBucket, ExceptionRow } from '@/types/scorecard'
import { Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ExceptionTable } from './ExceptionTable'
import { TierStrip } from './TierStrip'
import { Card, PanelHeader } from './primitives'


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
  const [queryError, setQueryError] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)

  const TOP_N = 5
  const shownBuckets = showAll ? buckets : buckets.slice(0, TOP_N)
  const hidden = Math.max(buckets.length - TOP_N, 0)

  // Debounced so typing does not fire a query per keystroke.
  useEffect(() => {
    const id = setTimeout(() => setFilter((f) => ({ ...f, search: search || null })), 180)
    return () => clearTimeout(id)
  }, [search])

  useEffect(() => {
    let cancelled = false
    queryExceptions(filter)
      .then((r) => {
        if (cancelled) return
        setQueryError(null)
        setRows(r)
        if (!filter.cls && !filter.tier && !filter.search) setTotal(r.length)
      })
      .catch((e: unknown) => {
        // A failed query must not read as "zero exceptions". This whole panel exists to
        // report an honest gap; silently showing an empty list is the one failure mode
        // that would misrepresent the run.
        if (cancelled) return
        setQueryError(e instanceof Error ? e.message : String(e))
        setRows([])
      })
    return () => {
      cancelled = true
    }
  }, [filter])

  const active = filter.cls || filter.tier || filter.search

  return (
    <Card className="flex h-full min-h-0 flex-col">
      <PanelHeader
        title="Every record we could not resolve, and why"
        note={
          <>
            Target 5–12% of the batch. A submission reporting zero exceptions is either lying or
            not trying. Currently{' '}
            <span className="num font-medium" style={{ color: 'var(--color-exception)' }}>
              {fmtPct(exceptionRatePct)}
            </span>{' '}
            of <span className="num">{fmtCount(totalRecords)}</span>.
          </>
        }
        right={
          <div className="relative">
            <Search
              size={13}
              className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2"
              style={{ color: 'var(--color-fg-faint)' }}
            />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="id, ledger, UTR…"
              className="w-56 rounded-lg border py-1.5 pr-2 pl-8 font-mono text-[0.6875rem] outline-none"
              style={{
                background: 'var(--color-inset)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-fg)',
              }}
            />
          </div>
        }
      />

      {/* Class chips, ordered by count — but only the top few by default. Eleven classes
          plus five tiers put sixteen controls in front of the reader before they had seen a
          single row; the long tail is a click away instead. */}
      <div className="hairline flex flex-wrap items-center gap-1.5 px-6 py-3.5">
        {shownBuckets.map((b) => {
          const on = filter.cls === b.cls
          return (
            <button
              key={b.cls}
              onClick={() => setFilter((f) => ({ ...f, cls: on ? null : b.cls }))}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[0.6875rem] transition-colors"
              style={
                on
                  ? { background: 'var(--color-accent)', color: 'var(--color-on-accent)' }
                  : { background: 'var(--color-inset)', color: 'var(--color-fg-muted)' }
              }
              title={`${fmtPaiseCompact(b.amount_paise)} · ${fmtPct(b.pct_of_batch)} of batch`}
            >
              <span>{EXCEPTION_LABEL[b.cls] ?? b.cls}</span>
              <span className="num opacity-65">{fmtCount(b.count)}</span>
            </button>
          )
        })}

        {hidden > 0 ? (
          <button
            onClick={() => setShowAll((v) => !v)}
            className="rounded-lg px-2.5 py-1.5 text-[0.6875rem] transition-colors"
            style={{ color: 'var(--color-fg-subtle)' }}
          >
            {showAll ? 'show less' : `+${hidden} more`}
          </button>
        ) : null}

        {active ? (
          <button
            onClick={() => {
              setFilter({})
              setSearch('')
              setShowAll(false)
            }}
            className="ml-auto flex items-center gap-1 text-[0.6875rem]"
            style={{ color: 'var(--color-fg-subtle)' }}
          >
            <X size={11} /> clear
          </button>
        ) : null}
      </div>

      <div className="hairline">
        <TierStrip
          filter={filter}
          onPick={(tier) => setFilter((f) => ({ ...f, tier }))}
        />
      </div>

      <div className="hairline min-h-0 flex-1">
        {queryError ? (
          <div
            className="flex h-full items-center justify-center px-6 text-center text-xs"
            style={{ color: 'var(--color-blocked)' }}
          >
            <div>
              <p className="font-medium">Exception query failed — this is not an empty list.</p>
              <pre
                className="mt-2 overflow-x-auto font-mono text-[0.6875rem]"
                style={{ color: 'var(--color-fg-subtle)' }}
              >
                {queryError}
              </pre>
            </div>
          </div>
        ) : (
          <ExceptionTable
            rows={rows}
            totalCount={total || rows.length}
            onSelect={onSelect}
            selectedId={selectedId}
          />
        )}
      </div>
    </Card>
  )
}
