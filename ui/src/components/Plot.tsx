import { token } from '@/lib/theme'
import * as Plot from '@observablehq/plot'
import { useEffect, useRef, useState } from 'react'

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
  const [width, setWidth] = useState(0)

  // Plot has no responsive mode: omit `width` and it renders at a fixed 640px, which leaves
  // a dead band down the right of any card wider than that. Measuring the container and
  // re-plotting on resize is the whole fix.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.round(entry.contentRect.width)
      // Ignore sub-pixel jitter, which would otherwise re-plot on every scroll frame.
      setWidth((prev) => (Math.abs(prev - w) > 1 ? w : prev))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const el = ref.current
    if (!el || width === 0) return
    const chart = Plot.plot({ ...options, width })
    el.append(chart)
    return () => chart.remove()
  }, [options, width])

  return <div ref={ref} className={className} />
}

/**
 * Shared Plot styling, resolved from the live design tokens.
 *
 * SVG marks cannot reference CSS custom properties, so callers must read this at render
 * time and key their `useMemo` on the current theme — that is what makes charts follow the
 * light/dark toggle instead of freezing on whichever theme loaded first.
 */
export function plotTheme(): Partial<Plot.PlotOptions> {
  return {
    style: {
      background: 'transparent',
      color: token('fg-muted'),
      fontFamily: 'JetBrains Mono, ui-monospace, monospace',
      fontSize: '11px',
      overflow: 'visible',
    },
  }
}

export function tierRange(): string[] {
  return [token('tier-0'), token('tier-1'), token('tier-2'), token('tier-3'), token('tier-4')]
}
