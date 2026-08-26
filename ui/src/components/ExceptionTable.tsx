import { cn } from '@/lib/cn'
import { EXCEPTION_LABEL, EXCEPTION_REALITY, fmtCount, fmtPaise } from '@/lib/format'
import type { ExceptionRow, MatchTierId } from '@/types/scorecard'
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import { ArrowDown, ArrowUp } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import { Badge, Empty, TierBadge } from './primitives'

const col = createColumnHelper<ExceptionRow>()

const ACTION_TONE: Record<string, 'matched' | 'exception' | 'blocked' | 'suppressed' | 'neutral'> = {
  cancel_dunning: 'matched',
  auto_apply: 'matched',
  suspend_dunning: 'matched',
  no_action: 'suppressed',
  human_queue: 'exception',
  pg_adjustment_query: 'neutral',
  credit_note: 'neutral',
}

/**
 * The exception list. Displayed by default, never behind a toggle (INAI_SPEC.md §9.6).
 *
 * Virtualised because `stress.yaml` is 25,000 records and a submission that reports zero
 * exceptions is either lying or not trying — so this table has to stay usable when it is
 * long, which is exactly when it matters.
 */
export function ExceptionTable({
  rows,
  totalCount,
  onSelect,
  selectedId,
}: {
  rows: ExceptionRow[]
  totalCount: number
  onSelect: (row: ExceptionRow) => void
  selectedId?: string | null
}) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'amount_paise', desc: true }])

  // The panel runs full width now, so the columns a reader needs to actually trace a
  // record are back: the settlement ref (the join key into the bank statement) and the
  // machine reason. The exception id and bank ref stay in the drawer — they identify a row
  // you have already found rather than helping you find it.
  const columns = useMemo(
    () => [
      col.accessor('cls', {
        header: 'Class',
        size: 180,
        cell: (c) => (
          <span
            className="block truncate font-medium"
            style={{ color: 'var(--color-fg)' }}
            title={EXCEPTION_REALITY[c.getValue()]}
          >
            {EXCEPTION_LABEL[c.getValue()] ?? c.getValue()}
          </span>
        ),
      }),
      col.accessor('tier', {
        header: 'Tier',
        size: 64,
        cell: (c) => <TierBadge tier={c.getValue() as MatchTierId} />,
      }),
      col.accessor('amount_paise', {
        header: 'Amount',
        size: 132,
        cell: (c) => (
          <span
            className="num block text-right font-medium"
            style={{ color: 'var(--color-fg-strong)' }}
          >
            {fmtPaise(c.getValue())}
          </span>
        ),
      }),
      col.accessor('ledger_ref', {
        header: 'Ledger',
        size: 116,
        cell: (c) => (
          <span className="num text-[0.6875rem]" style={{ color: 'var(--color-fg-subtle)' }}>
            {c.getValue()}
          </span>
        ),
      }),
      col.accessor('settlement_ref', {
        header: 'Settlement',
        size: 156,
        cell: (c) => (
          <span
            className="num block truncate text-[0.6875rem]"
            style={{ color: 'var(--color-fg-subtle)' }}
          >
            {c.getValue()}
          </span>
        ),
      }),
      col.accessor('routed_action', {
        header: 'Routed to',
        size: 162,
        cell: (c) => (
          <Badge tone={ACTION_TONE[c.getValue()] ?? 'neutral'}>
            {c.getValue().replaceAll('_', ' ')}
          </Badge>
        ),
      }),
      col.accessor('machine_reason', {
        header: 'Machine reason',
        size: 230,
        cell: (c) => (
          <span
            className="block truncate text-[0.6875rem]"
            style={{ color: 'var(--color-fg-faint)' }}
          >
            {c.getValue()}
          </span>
        ),
      }),
    ],
    [],
  )

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const parentRef = useRef<HTMLDivElement>(null)
  const modelRows = table.getRowModel().rows

  const virtualizer = useVirtualizer({
    count: modelRows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 12,
  })

  const items = virtualizer.getVirtualItems()
  const paddingTop = items.length ? items[0].start : 0
  const paddingBottom = items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0

  if (rows.length === 0) {
    return <Empty>No exceptions match this filter.</Empty>
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden"
        style={{ scrollbarGutter: 'stable' }}>
        <table className="w-full table-fixed border-collapse text-sm">
          {/* The sticky header needs an opaque background AND a shadow. With only a border,
              a row scrolled half-under it reads as a rendering fault rather than as content
              passing beneath a fixed header. */}
          <thead
            className="sticky top-0 z-20"
            style={{
              background: 'var(--color-card)',
              boxShadow: '0 1px 0 var(--color-border), 0 6px 10px -8px rgb(0 0 0 / 0.35)',
            }}
          >
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b" style={{ borderColor: 'var(--color-border)' }}>
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted()
                  const numeric = h.column.id === 'amount_paise'
                  return (
                    <th
                      key={h.id}
                      style={{ width: h.getSize(), color: 'var(--color-fg-subtle)' }}
                      onClick={h.column.getToggleSortingHandler()}
                      className={cn(
                        'cursor-pointer px-3 py-2.5 text-[0.6875rem] font-medium tracking-wide uppercase select-none',
                        numeric ? 'text-right' : 'text-left',
                      )}
                    >
                      <span
                        className={cn('inline-flex items-center gap-1', numeric && 'flex-row-reverse')}
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {sorted === 'asc' ? (
                          <ArrowUp size={11} />
                        ) : sorted === 'desc' ? (
                          <ArrowDown size={11} />
                        ) : null}
                      </span>
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {paddingTop > 0 && (
              <tr>
                <td colSpan={columns.length} style={{ height: paddingTop }} />
              </tr>
            )}
            {items.map((v) => {
              const row = modelRows[v.index]
              const selected = row.original.exception_id === selectedId
              return (
                <tr
                  key={row.id}
                  onClick={() => onSelect(row.original)}
                  className="cursor-pointer border-b transition-colors"
                  style={{
                    borderColor: 'var(--color-border-soft)',
                    background: selected ? 'var(--color-accent-soft)' : undefined,
                  }}
                  onMouseEnter={(e) => {
                    if (!selected) e.currentTarget.style.background = 'var(--color-inset)'
                  }}
                  onMouseLeave={(e) => {
                    if (!selected) e.currentTarget.style.background = ''
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="overflow-hidden px-3 py-2 whitespace-nowrap">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              )
            })}
            {paddingBottom > 0 && (
              <tr>
                <td colSpan={columns.length} style={{ height: paddingBottom }} />
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div
        className="hairline flex items-center justify-between px-5 py-2.5 text-[0.6875rem]"
        style={{ color: 'var(--color-fg-subtle)' }}
      >
        <span>
          <span className="num font-medium" style={{ color: 'var(--color-fg)' }}>
            {fmtCount(rows.length)}
          </span>{' '}
          shown
          {rows.length !== totalCount ? (
            <>
              {' '}
              of{' '}
              <span className="num" style={{ color: 'var(--color-fg-muted)' }}>
                {fmtCount(totalCount)}
              </span>
            </>
          ) : null}
        </span>
        <span>Rendered from Parquet via DuckDB-Wasm — no server</span>
      </div>
    </div>
  )
}
