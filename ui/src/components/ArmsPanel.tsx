import { ARM_LABEL, ARM_NOTE, fmtCI, fmtPaiseCompact, fmtPct, fmtPp } from '@/lib/format'
import type { RecoveryMetrics } from '@/types/scorecard'
import * as Plot from '@observablehq/plot'
import { AlertTriangle } from 'lucide-react'
import { useMemo } from 'react'
import { PLOT_THEME, PlotFigure } from './Plot'
import { Card, PanelHeader } from './primitives'

/**
 * Three arms and the confidence interval on the difference.
 *
 * The holdout bar is the honest one: it is the share that recovers with no intervention at
 * all, and it is the reason every gross vendor benchmark between 20% and 80% can be true
 * simultaneously. The headline is the *difference*, with an interval on it.
 */
export function ArmsPanel({ recovery }: { recovery: RecoveryMetrics }) {
  const ci = recovery.rate_difference_ci

  const armChart = useMemo<Plot.PlotOptions>(() => {
    const data = recovery.arms.map((a) => ({
      arm: ARM_LABEL[a.arm],
      rate: a.gross_recovery_rate_pct,
      isHoldout: a.arm === 'pure_holdout',
    }))
    return {
      ...PLOT_THEME,
      height: 132,
      marginLeft: 92,
      marginRight: 44,
      marginTop: 4,
      marginBottom: 24,
      x: { domain: [0, 100], label: 'gross recovery rate %', grid: true, ticks: 5 },
      y: { label: null, domain: data.map((d) => d.arm) },
      marks: [
        Plot.barX(data, {
          x: 'rate',
          y: 'arm',
          fill: (d: { isHoldout: boolean }) =>
            d.isHoldout ? 'oklch(0.552 0.014 286)' : 'oklch(0.72 0.16 248)',
          insetTop: 6,
          insetBottom: 6,
          rx: 2,
        }),
        Plot.text(data, {
          x: 'rate',
          y: 'arm',
          text: (d: { rate: number }) => `${d.rate.toFixed(1)}%`,
          dx: 16,
          fill: 'oklch(0.82 0.012 286)',
          fontSize: 11,
        }),
        Plot.ruleX([0]),
      ],
    }
  }, [recovery.arms])

  // The interval, drawn as an interval. This is the mark Recharts does not have.
  const ciChart = useMemo<Plot.PlotOptions>(() => {
    const span = Math.max(Math.abs(ci.low), Math.abs(ci.high)) * 1.35 + 1
    const d = [{ label: 'Agent − Control', ...ci }]
    return {
      ...PLOT_THEME,
      height: 74,
      marginLeft: 92,
      marginRight: 44,
      marginTop: 10,
      marginBottom: 26,
      x: { domain: [-span, span], label: 'difference in recovery rate (pp)', grid: true },
      y: { label: null, domain: d.map((x) => x.label) },
      marks: [
        // Zero line. If the bar touches it, the result is not a result.
        Plot.ruleX([0], { stroke: 'oklch(0.68 0.19 22)', strokeDasharray: '3,3', strokeWidth: 1.5 }),
        Plot.ruleY(d, {
          x1: 'low',
          x2: 'high',
          y: 'label',
          stroke: ci.crosses_zero ? 'oklch(0.68 0.19 22)' : 'oklch(0.75 0.16 152)',
          strokeWidth: 2.5,
          strokeLinecap: 'round',
        }),
        Plot.dot(d, {
          x: 'point',
          y: 'label',
          r: 4.5,
          fill: ci.crosses_zero ? 'oklch(0.68 0.19 22)' : 'oklch(0.75 0.16 152)',
        }),
        Plot.text(d, {
          x: 'high',
          y: 'label',
          text: () => fmtPp(ci.point),
          dx: 22,
          fill: 'oklch(0.82 0.012 286)',
          fontSize: 11,
        }),
      ],
    }
  }, [ci])

  return (
    <Card>
      <PanelHeader
        title="Three arms, and the interval on the difference"
        note="Agent 70% / Control 20% / Pure holdout 10%, stratified. The control arm runs without reconciliation — that is what makes false dunning countable."
      />

      <div className="hairline px-2 pt-2">
        <PlotFigure options={armChart} />
      </div>

      <div className="text-base-500 grid grid-cols-3 gap-2 px-4 pb-1 text-[0.6875rem]">
        {recovery.arms.map((a) => (
          <div key={a.arm} className="leading-snug">
            <span className="text-base-400 font-medium">{ARM_LABEL[a.arm]}</span>
            <br />
            {ARM_NOTE[a.arm]}
          </div>
        ))}
      </div>

      <div className="hairline mt-2 px-2 pt-2">
        <PlotFigure options={ciChart} />
      </div>

      <div className="hairline px-4 py-3">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2 text-xs">
          <span className="text-base-500">
            Self-cure{' '}
            <span className="num text-base-300">{fmtPct(recovery.self_cure_rate_pct)}</span>
          </span>
          <span className="text-base-500">
            Lift over baseline <span className="num text-base-300">{fmtPct(recovery.lift_pct)}</span>
          </span>
          <span className="text-base-500">
            Incremental{' '}
            <span className="num text-matched">
              {fmtPaiseCompact(recovery.incremental_vs_baseline_paise)}
            </span>
          </span>
          <span className="text-base-500">
            MDE <span className="num text-base-300">{recovery.mde_pp.toFixed(1)} pp</span>
          </span>
        </div>

        <p className="text-base-500 mt-2.5 text-xs leading-relaxed">
          95% CI on the rate difference{' '}
          <span className="num text-base-300">{fmtCI(ci.low, ci.high)}</span>, two-proportion z.
        </p>

        {ci.crosses_zero ? (
          <p className="text-blocked mt-2 flex items-start gap-1.5 text-xs leading-relaxed">
            <AlertTriangle size={14} className="mt-px shrink-0" />
            <span>
              This interval crosses zero. At this sample size the result is not statistically
              distinguishable from no effect, and it is reported that way rather than rounded up.
            </span>
          </p>
        ) : null}
      </div>
    </Card>
  )
}
