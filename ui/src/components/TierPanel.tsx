import { fmtCount, fmtPct, TIER_LABEL } from '@/lib/format'
import type { ReconMetrics } from '@/types/scorecard'
import { Card, Meter, PanelHeader, TierBadge } from './primitives'

/**
 * Match rate by difficulty tier. Never blended.
 *
 * The `proves` column is the point of this panel. A blended 91% is dominated by T0 exact-
 * reference matches that were never hard; showing T0 at ~100% next to the words "Nothing.
 * Say so on the slide." is what separates this from a vendor number.
 */
export function TierPanel({ recon }: { recon: ReconMetrics }) {
  return (
    <Card>
      <PanelHeader
        title="Match rate by difficulty tier"
        note="Never blended. Vendors publish one number dominated by exact-reference matches that were never hard."
        right={
          <div className="text-right">
            <div className="num text-sm font-medium" style={{ color: 'var(--color-fg-strong)' }}>
              {fmtPct(recon.auto_match_rate_pct)}
            </div>
            <div className="text-[0.6875rem]" style={{ color: 'var(--color-fg-subtle)' }}>
              auto-match (T0–T2)
            </div>
          </div>
        }
      />
      <div className="hairline">
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-[0.6875rem] tracking-wide uppercase"
              style={{ color: 'var(--color-fg-subtle)' }}
            >
              <th className="py-2 pr-2 pl-5 text-left font-medium">Tier</th>
              <th className="px-2 py-2 text-right font-medium" data-num>
                Eligible
              </th>
              <th className="px-2 py-2 text-right font-medium" data-num>
                Matched
              </th>
              <th className="px-2 py-2 text-right font-medium" data-num>
                Rate
              </th>
              <th className="w-[26%] px-3 py-2 text-left font-medium">vs target</th>
              <th className="py-2 pr-5 pl-2 text-left font-medium">What it proves</th>
            </tr>
          </thead>
          <tbody>
            {recon.tiers.map((t) => {
              const below = t.match_rate_pct < t.target_pct_low
              return (
                <tr
                  key={t.tier}
                  className="border-t"
                  style={{ borderColor: 'var(--color-border-soft)' }}
                >
                  <td className="py-2.5 pr-2 pl-5">
                    <div className="flex items-center gap-2">
                      <TierBadge tier={t.tier} />
                      <span
                        className="hidden text-xs sm:inline"
                        style={{ color: 'var(--color-fg-muted)' }}
                      >
                        {TIER_LABEL[t.tier].split(' · ')[1]}
                      </span>
                    </div>
                  </td>
                  <td
                    className="num px-2 py-2.5 text-right text-xs"
                    style={{ color: 'var(--color-fg-subtle)' }}
                  >
                    {fmtCount(t.eligible)}
                  </td>
                  <td
                    className="num px-2 py-2.5 text-right text-xs"
                    style={{ color: 'var(--color-fg)' }}
                  >
                    {fmtCount(t.matched)}
                  </td>
                  <td
                    className="num px-2 py-2.5 text-right text-xs font-semibold"
                    style={{ color: below ? 'var(--color-exception)' : 'var(--color-matched)' }}
                  >
                    {fmtPct(t.match_rate_pct)}
                  </td>
                  <td className="px-3 py-2.5">
                    <Meter
                      value={t.match_rate_pct}
                      target={[t.target_pct_low, t.target_pct_high]}
                      tone={below ? 'exception' : 'matched'}
                    />
                    <div
                      className="mt-1 font-mono text-[0.625rem]"
                      style={{ color: 'var(--color-fg-faint)' }}
                    >
                      target {t.target_pct_low.toFixed(0)}–{t.target_pct_high.toFixed(0)}%
                    </div>
                  </td>
                  <td
                    className="py-2.5 pr-5 pl-2 text-xs italic"
                    style={{ color: 'var(--color-fg-muted)' }}
                  >
                    {t.proves}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div
        className="hairline flex flex-wrap gap-x-6 gap-y-1 px-5 py-3 text-xs"
        style={{ color: 'var(--color-fg-subtle)' }}
      >
        <span>
          Overall{' '}
          <span className="num font-medium" style={{ color: 'var(--color-fg)' }}>
            {fmtPct(recon.overall_match_rate_pct)}
          </span>
        </span>
        <span>
          Exception rate{' '}
          <span className="num font-medium" style={{ color: 'var(--color-exception)' }}>
            {fmtPct(recon.exception_rate_pct)}
          </span>
        </span>
        <span>
          Residual explained{' '}
          <span className="num font-medium" style={{ color: 'var(--color-fg)' }}>
            {fmtPct(recon.residual_explained_pct)}
          </span>
        </span>
      </div>
    </Card>
  )
}
