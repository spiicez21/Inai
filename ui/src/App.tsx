import { ArmsPanel } from '@/components/ArmsPanel'
import { AuditDrawer } from '@/components/AuditDrawer'
import { BridgePanel } from '@/components/BridgePanel'
import { ExceptionsPanel } from '@/components/ExceptionsPanel'
import { PolicyPanel } from '@/components/PolicyPanel'
import { Badge, Card, Figure } from '@/components/primitives'
import { RunHeader } from '@/components/RunHeader'
import { NAV, Sidebar } from '@/components/Sidebar'
import { TierPanel } from '@/components/TierPanel'
import { fmtCount, fmtPaise, fmtPct } from '@/lib/format'
import { fetchLatestRunId, fetchScorecard, loadExceptions } from '@/lib/runs'
import { useTheme } from '@/lib/theme'
import type { ExceptionRow, Scorecard } from '@/types/scorecard'
import { AlertTriangle, Loader2, TrendingUp, Zap } from 'lucide-react'
import { useQueryState } from 'nuqs'
import { useCallback, useEffect, useRef, useState } from 'react'

export default function App() {
  // Run id and the selected record live in the URL: a judge's link reproduces exactly what
  // they were looking at, and the browser back button works through a drill-down.
  const [runId, setRunId] = useQueryState('run')
  const [selectedId, setSelectedId] = useQueryState('exc')

  const [scorecard, setScorecard] = useState<Scorecard | null>(null)
  const [selected, setSelected] = useState<ExceptionRow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState(false)
  const [active, setActive] = useState('overview')
  const { theme, toggle } = useTheme()

  const sections = useRef<Record<string, HTMLElement | null>>({})

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

  // Scroll-spy: the sidebar tracks what you are actually looking at, rather than only what
  // you last clicked.
  useEffect(() => {
    if (!scorecard) return
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (visible?.target.id) setActive(visible.target.id)
      },
      { rootMargin: '-15% 0px -60% 0px', threshold: [0.1, 0.5] },
    )
    for (const item of NAV) {
      const el = sections.current[item.id]
      if (el) obs.observe(el)
    }
    return () => obs.disconnect()
  }, [scorecard])

  const navigate = useCallback((id: string) => {
    setActive(id)
    sections.current[id]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const register = useCallback(
    (id: string) => (el: HTMLElement | null) => {
      sections.current[id] = el
    },
    [],
  )

  if (error) return <Fatal message={error} />
  if (!scorecard) return <Loading />

  const { meta, recon, recovery, bridge, exceptions, policy_blocks } = scorecard
  const placeholder = scorecard.limitations.find((l) => l.startsWith('PLACEHOLDER RUN'))
  const totalExceptions = exceptions.reduce((n, b) => n + b.count, 0)

  return (
    <div className="flex min-h-dvh gap-5 p-5">
      <Sidebar
        active={active}
        onNavigate={navigate}
        counts={{
          exceptions: totalExceptions,
          policy: policy_blocks.length,
          tiers: recon.tiers.length,
        }}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        theme={theme}
        onToggleTheme={toggle}
      />

      <main className="min-w-0 flex-1">
        <RunHeader meta={meta} />

        {placeholder ? (
          <div
            className="mb-5 flex items-start gap-2.5 rounded-2xl px-4 py-3.5 text-xs leading-relaxed"
            style={{ background: 'var(--color-exception-soft)', color: 'var(--color-exception)' }}
          >
            <AlertTriangle size={14} className="mt-px shrink-0" />
            <span>{placeholder}</span>
          </div>
        ) : null}

        <div className="flex flex-col gap-6">
          {/* Headline row. The holdout tile sits next to the agent tile deliberately —
              the self-cure rate is the context that makes the agent number honest. */}
          <section id="overview" ref={register('overview')} className="scroll-mt-4">
            <div className="grid gap-5 lg:grid-cols-[1.15fr_1fr_1fr]">
              <Card className="p-6">
                <div className="flex items-start justify-between">
                  <span className="eyebrow">Incremental vs baseline</span>
                  <Badge tone="matched" icon={<TrendingUp size={11} />}>
                    {fmtPct(recovery.lift_pct)} lift
                  </Badge>
                </div>
                <div className="mt-4">
                  <Figure
                    value={fmtPaise(recovery.incremental_vs_baseline_paise)}
                    className="text-[2.5rem] leading-none"
                  />
                </div>
                <p className="mt-2 text-xs" style={{ color: 'var(--color-fg-subtle)' }}>
                  Treatment minus randomised control — not a gross recovery number.
                </p>
                <div className="mt-5">
                  <Badge tone={recovery.rate_difference_ci.crosses_zero ? 'blocked' : 'matched'}>
                    95% CI {recovery.rate_difference_ci.low.toFixed(1)} to{' '}
                    {recovery.rate_difference_ci.high.toFixed(1)} pp
                  </Badge>
                </div>
              </Card>

              <Card className="p-6">
                <span className="eyebrow">Recovery rate by arm</span>
                <div className="mt-3">
                  <Figure value={fmtPct(recovery.agent_rate_pct)} className="text-[2rem] leading-none" />
                </div>
                <div className="mt-5 space-y-3">
                  <ArmBar label="Agent" pct={recovery.agent_rate_pct} tone="var(--color-accent)" />
                  <ArmBar
                    label="Control"
                    pct={recovery.baseline_rate_pct}
                    tone="var(--color-lime)"
                  />
                  <ArmBar
                    label="Holdout"
                    pct={recovery.self_cure_rate_pct}
                    tone="var(--color-fg-faint)"
                    note="self-cure"
                  />
                </div>
              </Card>

              <Card className="p-6">
                <div className="flex items-start justify-between">
                  <span className="eyebrow">Auto-match T0–T2</span>
                  <Badge tone="lime" icon={<Zap size={11} />}>
                    vendor-comparable
                  </Badge>
                </div>
                <div className="mt-3">
                  <Figure
                    value={fmtPct(recon.auto_match_rate_pct)}
                    className="text-[2rem] leading-none"
                  />
                </div>
                <p className="mt-3 text-xs" style={{ color: 'var(--color-fg-subtle)' }}>
                  Dominated by exact-reference matches that were never hard. The tier
                  breakdown below is the honest read.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Badge tone="exception">
                    {fmtCount(totalExceptions)} exceptions · {fmtPct(recon.exception_rate_pct)}
                  </Badge>
                  <Badge tone="neutral">{fmtCount(scorecard.unresolved_count)} unresolved</Badge>
                </div>
              </Card>
            </div>
          </section>

          <section id="bridge" ref={register('bridge')} className="scroll-mt-4">
            <BridgePanel bridge={bridge} />
          </section>

          <div className="grid gap-6 2xl:grid-cols-2">
            <section id="tiers" ref={register('tiers')} className="scroll-mt-4">
              <TierPanel recon={recon} />
            </section>
            <section id="arms" ref={register('arms')} className="scroll-mt-4">
              <ArmsPanel recovery={recovery} theme={theme} />
            </section>
          </div>

          {/* Exceptions runs full width. It is the artifact the whole submission turns on,
              and at half width its table could not carry the settlement ref or the machine
              reason without a horizontal scrollbar. Policy and limitations sit beneath it —
              they are supporting evidence, not peers competing for the same row. */}
          <section
            id="exceptions"
            ref={register('exceptions')}
            className="h-[42rem] min-w-0 scroll-mt-4"
          >
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
          </section>

          <section id="policy" ref={register('policy')} className="min-w-0 scroll-mt-4">
            <PolicyPanel blocks={policy_blocks} />
          </section>
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

function ArmBar({
  label,
  pct,
  tone,
  note,
}: {
  label: string
  pct: number
  tone: string
  note?: string
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-[0.6875rem]">
        <span style={{ color: 'var(--color-fg-muted)' }}>
          {label}
          {note ? (
            <span style={{ color: 'var(--color-fg-faint)' }}> · {note}</span>
          ) : null}
        </span>
        <span className="num font-medium" style={{ color: 'var(--color-fg)' }}>
          {fmtPct(pct)}
        </span>
      </div>
      <div
        className="mt-1 h-2 overflow-hidden rounded-full"
        style={{ background: 'var(--color-inset)' }}
      >
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: tone }} />
      </div>
    </div>
  )
}

function Loading() {
  return (
    <div
      className="flex min-h-dvh items-center justify-center gap-2 text-sm"
      style={{ color: 'var(--color-fg-subtle)' }}
    >
      <Loader2 size={15} className="animate-spin" />
      Loading run artifacts…
    </div>
  )
}

function Fatal({ message }: { message: string }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-6">
      <div className="max-w-md text-center">
        <AlertTriangle size={20} style={{ color: 'var(--color-exception)' }} className="mx-auto" />
        <p className="mt-3 text-sm" style={{ color: 'var(--color-fg)' }}>
          {message}
        </p>
        <pre
          className="mt-4 overflow-x-auto rounded-xl px-3.5 py-2.5 text-left font-mono text-[0.6875rem]"
          style={{ background: 'var(--color-card)', color: 'var(--color-fg-muted)' }}
        >
          uv run inai run --config configs/demo.yaml --seed 42
        </pre>
      </div>
    </div>
  )
}
