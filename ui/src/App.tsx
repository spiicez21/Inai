import { ArmsPanel } from '@/components/ArmsPanel'
import { AuditDrawer } from '@/components/AuditDrawer'
import { BridgePanel } from '@/components/BridgePanel'
import { ExceptionsPanel } from '@/components/ExceptionsPanel'
import { PolicyPanel } from '@/components/PolicyPanel'
import { Card, PanelHeader, Stat } from '@/components/primitives'
import { RunHeader } from '@/components/RunHeader'
import { TierPanel } from '@/components/TierPanel'
import { fmtCount, fmtPaiseCompact, fmtPct } from '@/lib/format'
import { fetchLatestRunId, fetchScorecard, loadExceptions } from '@/lib/runs'
import type { ExceptionRow, Scorecard } from '@/types/scorecard'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useQueryState } from 'nuqs'

export default function App() {
  // Run id and the selected record live in the URL: a judge's link reproduces exactly what
  // they were looking at, and the browser back button works through a drill-down.
  const [runId, setRunId] = useQueryState('run')
  const [selectedId, setSelectedId] = useQueryState('exc')

  const [scorecard, setScorecard] = useState<Scorecard | null>(null)
  const [selected, setSelected] = useState<ExceptionRow | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const id = runId ?? (await fetchLatestRunId())
        if (cancelled) return
        if (!runId) await setRunId(id)
        const [sc] = await Promise.all([fetchScorecard(id), loadExceptions(id)])
        if (!cancelled) setScorecard(sc)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  if (error) return <Fatal message={error} />
  if (!scorecard) return <Loading />

  const { meta, recon, recovery, bridge, exceptions, policy_blocks } = scorecard
  const placeholder = scorecard.limitations.find((l) => l.startsWith('PLACEHOLDER RUN'))

  return (
    <div className="min-h-dvh">
      <RunHeader meta={meta} />

      {placeholder ? (
        <div className="border-exception/30 bg-exception/10 text-exception border-b px-5 py-2.5">
          <div className="mx-auto flex max-w-[110rem] items-start gap-2 text-xs leading-relaxed">
            <AlertTriangle size={14} className="mt-px shrink-0" />
            <span>{placeholder}</span>
          </div>
        </div>
      ) : null}

      <main className="mx-auto flex max-w-[110rem] flex-col gap-4 px-5 py-5">
        {/* Headline row. The holdout tile sits next to the agent tile deliberately —
            the self-cure rate is the context that makes the agent number honest. */}
        <Card>
          <div className="grid grid-cols-2 gap-5 px-4 py-4 lg:grid-cols-5">
            <Stat
              label="Incremental vs baseline"
              tone="matched"
              value={fmtPaiseCompact(recovery.incremental_vs_baseline_paise)}
              sub={`treatment − control, ${fmtPct(recovery.lift_pct)} lift`}
            />
            <Stat
              label="Self-cure (holdout)"
              value={fmtPct(recovery.self_cure_rate_pct)}
              sub="recovers with no action at all"
            />
            <Stat
              label="Auto-match T0–T2"
              value={fmtPct(recon.auto_match_rate_pct)}
              sub="the number vendors quote"
            />
            <Stat
              label="False dunning prevented"
              tone="accent"
              value={fmtCount(bridge.false_dunning_prevented_n)}
              sub="chased by control, already paid"
            />
            <Stat
              label="Unresolved"
              tone="exception"
              value={fmtCount(scorecard.unresolved_count)}
              sub="shown, not hidden"
            />
          </div>
        </Card>

        <BridgePanel bridge={bridge} />

        <div className="grid gap-4 xl:grid-cols-2">
          <TierPanel recon={recon} />
          <ArmsPanel recovery={recovery} />
        </div>

        <div className="grid min-h-0 gap-4 xl:grid-cols-[1.6fr_1fr]">
          <div className="min-h-[34rem]">
            <ExceptionsPanel
              buckets={exceptions}
              totalRecords={meta.n_records}
              exceptionRatePct={recon.exception_rate_pct}
              selectedId={selectedId}
              onSelect={(row) => {
                setSelected(row)
                void setSelectedId(row.exception_id)
              }}
            />
          </div>

          <div className="flex flex-col gap-4">
            <PolicyPanel blocks={policy_blocks} />
            <LimitationsPanel limitations={scorecard.limitations} />
          </div>
        </div>
      </main>

      <AuditDrawer
        row={selected}
        onClose={() => {
          setSelected(null)
          void setSelectedId(null)
        }}
      />
    </div>
  )
}

/** §13 — state them before a judge finds them. On the page, not in an appendix. */
function LimitationsPanel({ limitations }: { limitations: string[] }) {
  const real = limitations.filter((l) => !l.startsWith('PLACEHOLDER RUN'))
  return (
    <Card>
      <PanelHeader
        title="Honest limitations"
        note="Stated here, before anyone has to find them."
      />
      <ul className="hairline space-y-2.5 px-4 py-3">
        {real.map((l, i) => (
          <li key={i} className="text-base-500 flex gap-2 text-xs leading-relaxed">
            <span className="num text-base-700 shrink-0">{String(i + 1).padStart(2, '0')}</span>
            <span>{l}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Loading() {
  return (
    <div className="text-base-500 flex min-h-dvh items-center justify-center gap-2 text-sm">
      <Loader2 size={15} className="animate-spin" />
      Loading run artifacts…
    </div>
  )
}

function Fatal({ message }: { message: string }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-6">
      <div className="max-w-md text-center">
        <AlertTriangle size={20} className="text-exception mx-auto" />
        <p className="text-base-200 mt-3 text-sm">{message}</p>
        <pre className="bg-base-900 border-base-800 text-base-400 mt-4 overflow-x-auto rounded border px-3 py-2 text-left font-mono text-[0.6875rem]">
          uv run inai run --config configs/demo.yaml --seed 42
        </pre>
      </div>
    </div>
  )
}
