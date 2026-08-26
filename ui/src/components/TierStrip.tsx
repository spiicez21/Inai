import { fmtCount, fmtPaiseCompact, TIER_SHORT } from '@/lib/format'
import { queryByTier, type ExceptionFilter, type TierBucket } from '@/lib/runs'
import type { MatchTierId } from '@/types/scorecard'
import { useEffect, useState } from 'react'

const TIERS: MatchTierId[] = [
  't0_exact',
  't1_deterministic',
  't2_fuzzy',
  't3_structural',
  't4_adversarial',
]

const TIER_NAME: Record<MatchTierId, string> = {
  t0_exact: 'exact',
  t1_deterministic: 'deterministic',
  t2_fuzzy: 'fuzzy',
  t3_structural: 'structural',
  t4_adversarial: 'adversarial',
}

const TIER_VAR: Record<MatchTierId, string> = {
  t0_exact: 'tier-0',
  t1_deterministic: 'tier-1',
  t2_fuzzy: 'tier-2',
  t3_structural: 'tier-3',
  t4_adversarial: 'tier-4',
}

/**
 * Where the unresolved records actually sit on the difficulty ramp.
 *
 * This replaces the row of five T0–T4 chips. Those were controls that showed nothing: you
 * could filter by tier but could not see which tier the failures were concentrated in —
 * which is the single most informative thing about an exception list. The bars are the
 * filter, so the control and the information are the same object.
 *
 * Hand-drawn in CSS rather than Plot: five bars need no scales, and this way they animate,
 * take a click, and follow the theme through CSS variables with no re-render.
 */
export function TierStrip({
  filter,
  onPick,
}: {
  filter: ExceptionFilter
  onPick: (tier: string | null) => void
}) {
  const [buckets, setBuckets] = useState<TierBucket[]>([])

  useEffect(() => {
    let cancelled = false
    // Deliberately keyed on class/search only, NOT on the tier filter: the strip must keep
    // showing the whole distribution while one of its own bars is selected, or picking a
    // tier would collapse the chart that shows you the tiers.
    queryByTier({ cls: filter.cls, search: filter.search })
      .then((b) => !cancelled && setBuckets(b))
      .catch(() => !cancelled && setBuckets([]))
    return () => {
      cancelled = true
    }
  }, [filter.cls, filter.search])

  const byTier = new Map(buckets.map((b) => [b.tier, b]))
  const max = Math.max(1, ...buckets.map((b) => b.n))
  const total = buckets.reduce((n, b) => n + b.n, 0)

  return (
    <div className="px-6 pt-3 pb-4">
      <div className="mb-3 flex items-baseline justify-between">
        <span className="eyebrow">Unresolved by difficulty tier</span>
        <span className="text-[0.6875rem]" style={{ color: 'var(--color-fg-faint)' }}>
          click a bar to filter
        </span>
      </div>

      <div className="flex items-end gap-2" style={{ height: 118 }}>
        {TIERS.map((t) => {
          const b = byTier.get(t)
          const n = b?.n ?? 0
          const on = filter.tier === t
          const dim = filter.tier != null && !on
          const pctOfMax = (n / max) * 100
          return (
            <button
              key={t}
              onClick={() => onPick(on ? null : t)}
              title={`${TIER_SHORT[t]} · ${TIER_NAME[t]} — ${fmtCount(n)} exceptions, ${fmtPaiseCompact(
                b?.amount_paise ?? 0,
              )}${total ? ` · ${((n / total) * 100).toFixed(0)}% of the list` : ''}`}
              className="group flex h-full flex-1 flex-col gap-1.5 transition-opacity"
              style={{ opacity: dim ? 0.35 : 1 }}
            >
              <span
                className="num shrink-0 text-center text-[0.6875rem] font-medium tabular-nums"
                style={{ color: on ? `var(--color-${TIER_VAR[t]})` : 'var(--color-fg-muted)' }}
              >
                {fmtCount(n)}
              </span>
              {/* The bar is absolutely positioned inside a flex-1 track. A percentage height
                  on a flex ITEM has no definite parent to resolve against and collapses to
                  nothing; against a positioned ancestor it resolves correctly. */}
              <span className="relative min-h-0 w-full flex-1">
                <span
                  className="absolute inset-x-0 bottom-0 rounded-md transition-all duration-500"
                  style={{
                    // A floor of 4% so an empty tier stays a visible, clickable target
                    // rather than a gap the eye reads as a missing category.
                    height: `${Math.max(pctOfMax, 4)}%`,
                    background: `var(--color-${TIER_VAR[t]})`,
                    outline: on ? '2px solid var(--color-fg-strong)' : undefined,
                    outlineOffset: 2,
                  }}
                />
              </span>
              <span
                className="num text-center text-[0.625rem]"
                style={{ color: on ? 'var(--color-fg)' : 'var(--color-fg-faint)' }}
              >
                {TIER_SHORT[t]}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
