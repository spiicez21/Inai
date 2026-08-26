import { ARM_LABEL, fmtCI, fmtPp } from '@/lib/format'
import { token, type Theme } from '@/lib/theme'
import type { RecoveryMetrics } from '@/types/scorecard'
import * as Plot from '@observablehq/plot'
import { AlertTriangle } from 'lucide-react'
import { useMemo } from 'react'
import { PlotFigure, plotTheme } from './Plot'
import { Card, PanelHeader } from './primitives'

/**
 * Three arms and the confidence interval on the difference.
 *
 * The holdout bar is the honest one: it is the share that recovers with no intervention at
 * all, and it is the reason every gross vendor benchmark between 20% and 80% can be true
 * simultaneously. The headline is the *difference*, with an interval on it.
 *
 * Both charts key their memo on `theme` — SVG marks take literal colours, so they have to
 * be rebuilt when the tokens change.
 */
export function ArmsPanel({ recovery, theme }: { recovery: RecoveryMetrics; theme: Theme }) {
  const ci = recovery.rate_difference_ci

  const armChart = useMemo<Plot.PlotOptions>(() => {
    const data = recovery.arms.map((a) => ({
      arm: ARM_LABEL[a.arm],
      rate: a.gross_recovery_rate_pct,
      isHoldout: a.arm === 'pure_holdout',
    }))
    const holdout = recovery.self_cure_rate_pct
    return {
      ...plotTheme(),
      height: 168,
      marginLeft: 88,
      marginRight: 26,
      marginTop: 8,
      marginBottom: 26,
      x: { domain: [0, 100], label: null, grid: true, ticks: 5, tickFormat: (d: number) => `${d}%` },
      y: { label: null, domain: data.map((d) => d.arm), padding: 0.34 },
      marks: [
        // The track behind each bar. Gives the bars a container to sit in, so a 33% bar
        // reads as "a third of the way" rather than just "short".
        Plot.barX(data, {
          x: 100,
          y: 'arm',
          fill: token('inset'),
          rx: 6,
        }),
        Plot.barX(data, {
          x: 'rate',
          y: 'arm',
          fill: (d: { isHoldout: boolean }) => (d.isHoldout ? token('fg-faint') : token('accent')),
          rx: 6,
        }),
        // Self-cure reference line across all three bars: everything to its left would have
        // recovered anyway. It is the single most clarifying mark on this chart.
        Plot.ruleX([holdout], {
          stroke: token('fg-muted'),
          strokeDasharray: '3,3',
          strokeWidth: 1.25,
        }),
        Plot.text(data, {
          x: 'rate',
          y: 'arm',
          text: (d: { rate: number }) => `${d.rate.toFixed(1)}%`,
          textAnchor: 'end',
          dx: -8,
          fill: (d: { isHoldout: boolean }) =>
            d.isHoldout ? token('fg-strong') : token('on-accent'),
          fontSize: 12,
          fontWeight: 600,
        }),
        Plot.text([{ x: holdout }], {
          x: 'x',
          frameAnchor: 'top',
          text: () => 'self-cure',
          dy: -2,
          dx: 26,
          fill: token('fg-subtle'),
          fontSize: 10,
        }),
      ],
    }
  }, [recovery.arms, recovery.self_cure_rate_pct, theme])

  // The interval, drawn as an interval. This is the mark Recharts does not have.
  const ciChart = useMemo<Plot.PlotOptions>(() => {
    const span = Math.max(Math.abs(ci.low), Math.abs(ci.high)) * 1.5 + 1
    const d = [{ label: 'Agent − Control', ...ci }]
    const stroke = ci.crosses_zero ? token('blocked') : token('matched')
    return {
      ...plotTheme(),
      height: 104,
      marginLeft: 88,
      marginRight: 26,
      marginTop: 26,
      marginBottom: 30,
      x: {
        domain: [-span, span],
        label: null,
        grid: true,
        tickFormat: (v: number) => `${v > 0 ? '+' : ''}${v}`,
      },
      y: { label: null, domain: d.map((x) => x.label) },
      marks: [
        // Zero line. If the interval touches it, the result is not a result.
        Plot.ruleX([0], { stroke: token('blocked'), strokeDasharray: '4,3', strokeWidth: 1.5 }),
        Plot.text([{}], {
          frameAnchor: 'top-left',
          text: () => 'no effect',
          dx: 4,
          dy: -14,
          fill: token('fg-faint'),
          fontSize: 10,
        }),
        // Whisker caps make the interval read as bounded rather than as a fading gradient.
        Plot.ruleY(d, { x1: 'low', x2: 'high', y: 'label', stroke, strokeWidth: 3, strokeLinecap: 'round' }),
        Plot.tickX(d, { x: 'low', y: 'label', stroke, strokeWidth: 2, inset: 12 }),
        Plot.tickX(d, { x: 'high', y: 'label', stroke, strokeWidth: 2, inset: 12 }),
        Plot.dot(d, { x: 'point', y: 'label', r: 5.5, fill: stroke, stroke: token('card'), strokeWidth: 2 }),
        Plot.text(d, {
          x: 'point',
          y: 'label',
          text: () => fmtPp(ci.point),
          dy: -18,
          fill: token('fg-strong'),
          fontSize: 12,
          fontWeight: 600,
        }),
      ],
    }
  }, [ci, theme])

  return (
    <Card>
      <PanelHeader
        title="Three arms, and the interval on the difference"
        note="Agent 70% / Control 20% / Pure holdout 10%, stratified. The control arm runs without reconciliation — that is what makes false dunning countable."
      />

      <div className="px-3 pt-1">
        <PlotFigure options={armChart} />
      </div>

      <div className="px-6 pt-4">
        <PlotFigure options={ciChart} />
      </div>

      {/* One sentence, not a metric strip. Self-cure, lift and incremental already appear
          in the overview row — repeating them here was noise, not rigour. */}
      <div className="px-6 pt-2 pb-6">
        <p className="text-xs leading-relaxed" style={{ color: 'var(--color-fg-subtle)' }}>
          95% CI on the rate difference{' '}
          <span className="num" style={{ color: 'var(--color-fg)' }}>
            {fmtCI(ci.low, ci.high)}
          </span>
          , two-proportion z · MDE {recovery.mde_pp.toFixed(1)} pp
        </p>

        {ci.crosses_zero ? (
          <p
            className="mt-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-xs leading-relaxed"
            style={{ background: 'var(--color-blocked-soft)', color: 'var(--color-blocked)' }}
          >
            <AlertTriangle size={14} className="mt-px shrink-0" />
            <span>
              This interval crosses zero — not statistically distinguishable from no effect at this
              sample size, and reported that way rather than rounded up.
            </span>
          </p>
        ) : null}
      </div>
    </Card>
  )
}
