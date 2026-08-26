import * as Plot from '@observablehq/plot'
import { useEffect, useRef } from 'react'

/**
 * Observable Plot mounted into a ref. Plot renders imperatively to an SVG node, so this is
 * the whole integration — no wrapper library, no React reconciliation of chart internals.
 *
 * Chosen over Recharts specifically because this dashboard's charts are statistical:
 * confidence intervals with error bars, and small multiples faceted by difficulty tier.
 * Recharts has no error-bar mark, so both would have been hand-rolled SVG.
 */
export function PlotFigure({
  options,
  className,
}: {
  options: Plot.PlotOptions
  className?: string
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const chart = Plot.plot(options)
    el.append(chart)
    return () => chart.remove()
  }, [options])

  return <div ref={ref} className={className} />
}

/** Shared Plot styling so every chart in the dashboard reads as one system. */
export const PLOT_THEME = {
  style: {
    background: 'transparent',
    color: 'oklch(0.82 0.012 286)',
    fontFamily: 'JetBrains Mono, ui-monospace, monospace',
    fontSize: '11px',
    overflow: 'visible',
  },
} satisfies Partial<Plot.PlotOptions>

export const TIER_RANGE = [
  'oklch(0.85 0.05 248)',
  'oklch(0.74 0.09 248)',
  'oklch(0.63 0.13 248)',
  'oklch(0.52 0.15 262)',
  'oklch(0.44 0.17 288)',
]
