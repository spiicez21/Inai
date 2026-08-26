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

  const columns = useMemo(
    () => [
      col.accessor('exception_id', {
        header: 'ID',
        size: 108,
        cell: (c) => <span className="num text-base-500 text-[0.6875rem]">{c.getValue()}</span>,
      }),
      col.accessor('cls', {
        header: 'Class',
        size: 190,
        cell: (c) => (
          <span className="text-base-200 truncate" title={EXCEPTION_REALITY[c.getValue()]}>
            {EXCEPTION_LABEL[c.getValue()] ?? c.getValue()}
          </span>
        ),
      }),
      col.accessor('tier', {
        header: 'Tier',
        size: 62,
        cell: (c) => <TierBadge tier={c.getValue() as MatchTierId} />,
      }),
      col.accessor('amount_paise', {
        header: 'Amount',
        size: 128,
        cell: (c) => (
          <span className="num text-base-100 block text-right">{fmtPaise(c.getValue())}</span>
        ),
      }),
      col.accessor('ledger_ref', {
        header: 'Ledger',
        size: 108,
        cell: (c) => <span className="num text-base-400 text-[0.6875rem]">{c.getValue()}</span>,
      }),
      col.accessor('settlement_ref', {
        header: 'Settlement',
        size: 148,
        cell: (c) => (
          <span className="num text-base-400 truncate text-[0.6875rem]">{c.getValue()}</span>
        ),
      }),
      col.accessor('routed_action', {
        header: 'Routed to',
        size: 156,
        cell: (c) => (
          <Badge tone={ACTION_TONE[c.getValue()] ?? 'neutral'}>
            {c.getValue().replaceAll('_', ' ')}
          </Badge>
        ),
      }),
      col.accessor('machine_reason', {
        header: 'Reason',
        size: 240,
        cell: (c) => (
          <span className="text-base-500 truncate text-[0.6875rem]">{c.getValue()}</span>
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
    estimateSize: () => 34,
    overscan: 12,
  })

  const items = virtualizer.getVirtualItems()
  const paddingTop = items.length ? items[0].start : 0
  const paddingBottom = items.length
    ? virtualizer.getTotalSize() - items[items.length - 1].end
    : 0

  if (rows.length === 0) {
    return <Empty>No exceptions match this filter.</Empty>
  }

  return (
    <div className="flex min-h-0 flex-col">
      <div ref={parentRef} className="min-h-0 flex-1 overflow-auto">
        <table className="w-full table-fixed border-collapse text-sm">
          <thead className="bg-base-900 sticky top-0 z-10">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-base-800 border-b">
                {hg.headers.map((h) => {
                  const sorted = h.column.getIsSorted()
                  const numeric = h.column.id === 'amount_paise'
                  return (
                    <th
                      key={h.id}
                      style={{ width: h.getSize() }}
                      onClick={h.column.getToggleSortingHandler()}
                      className={cn(
                        'text-base-500 hover:text-base-300 cursor-pointer px-2.5 py-2 text-[0.6875rem] font-medium tracking-wide uppercase select-none',
                        numeric ? 'text-right' : 'text-left',
                      )}
                    >
                      <span
                        className={cn(
                          'inline-flex items-center gap-1',
                          numeric && 'flex-row-reverse',
                        )}
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
                  className={cn(
                    'border-base-850/60 hover:bg-base-850/60 cursor-pointer border-b',
                    selected && 'bg-accent-bg/40 hover:bg-accent-bg/50',
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="overflow-hidden px-2.5 py-1.5 whitespace-nowrap">
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

      <div className="hairline text-base-500 flex items-center justify-between px-4 py-2 text-[0.6875rem]">
        <span>
          <span className="num text-base-300">{fmtCount(rows.length)}</span> shown
          {rows.length !== totalCount ? (
            <>
              {' '}
              of <span className="num text-base-300">{fmtCount(totalCount)}</span>
            </>
          ) : null}
        </span>
        <span>Rendered from Parquet via DuckDB-Wasm — no server</span>
      </div>
    </div>
  )
}
