import { fmtCount, fmtPaiseCompact } from '@/lib/format'
import type { PolicyBlock } from '@/types/scorecard'
import { ShieldCheck } from 'lucide-react'
import { Card, Empty, PanelHeader } from './primitives'

/**
 * Blocked actions, by rule. INAI_SPEC.md §8.5.
 *
 * Every one of these is an action the agent wanted to take and a named rule that stopped it.
 * Showing "we wanted to call this payer, and here is the rule that stopped us" demonstrates
 * bounded autonomy far better than never proposing the call.
 *
 * Each row carries a proportional bar. A bare column of counts makes the reader do the
 * arithmetic to work out which rule is actually load-bearing; the bar answers that before
 * they have finished reading the rule text.
 *
 * POL-RECON-001 is highlighted because it is the rule that only exists because Stage 1
 * exists — money arrived, so no dunning may fire, regardless of what the ledger says.
 */
export function PolicyPanel({ blocks }: { blocks: PolicyBlock[] }) {
  const sorted = [...blocks].sort((a, b) => b.blocked_count - a.blocked_count)
  const max = Math.max(1, ...sorted.map((b) => b.blocked_count))
  const total = sorted.reduce((n, b) => n + b.blocked_count, 0)

  return (
    <Card>
      <PanelHeader
        title="Actions blocked, by rule"
        note="Logged, never silently dropped. Each verdict carries a rule ID, the rule text and a remediation."
        right={
          <div className="flex items-center gap-2">
            <span className="num text-sm font-semibold" style={{ color: 'var(--color-fg-strong)' }}>
              {fmtCount(total)}
            </span>
            <ShieldCheck size={15} style={{ color: 'var(--color-fg-faint)' }} />
          </div>
        }
      />
      <div className="hairline">
        {sorted.length === 0 ? (
          <Empty>No actions blocked in this run.</Empty>
        ) : (
          // Two columns once there is room. At full width a single stacked list of eight
          // rules becomes a long thin ribbon with dead space beside it.
          <ul className="grid gap-x-8 px-6 py-1 lg:grid-cols-2">
            {sorted.map((b) => {
              const isBridgeRule = b.rule_id === 'POL-RECON-001'
              return (
                <li
                  key={b.rule_id}
                  className="border-b py-3"
                  style={{ borderColor: 'var(--color-border-soft)' }}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span
                      className="num shrink-0 rounded-md px-1.5 py-0.5 text-[0.625rem] font-medium"
                      style={
                        isBridgeRule
                          ? { background: 'var(--color-accent)', color: 'var(--color-on-accent)' }
                          : { background: 'var(--color-inset)', color: 'var(--color-fg-muted)' }
                      }
                    >
                      {b.rule_id}
                    </span>
                    <span className="flex shrink-0 items-baseline gap-2">
                      <span
                        className="num text-sm font-semibold"
                        style={{ color: 'var(--color-blocked)' }}
                      >
                        {fmtCount(b.blocked_count)}
                      </span>
                      <span
                        className="num text-[0.625rem]"
                        style={{ color: 'var(--color-fg-faint)' }}
                      >
                        {fmtPaiseCompact(b.amount_affected_paise)}
                      </span>
                    </span>
                  </div>

                  <p className="mt-1.5 text-xs leading-snug" style={{ color: 'var(--color-fg)' }}>
                    {b.rule_text}
                  </p>

                  <div
                    className="mt-2 h-1.5 overflow-hidden rounded-full"
                    style={{ background: 'var(--color-inset)' }}
                  >
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${(b.blocked_count / max) * 100}%`,
                        background: isBridgeRule ? 'var(--color-accent)' : 'var(--color-blocked)',
                        opacity: isBridgeRule ? 1 : 0.5,
                      }}
                    />
                  </div>

                  {isBridgeRule ? (
                    <p
                      className="mt-2 text-[0.6875rem] leading-snug"
                      style={{ color: 'var(--color-accent)' }}
                    >
                      Only exists because Stage 1 exists. Point at it in the demo.
                    </p>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Card>
  )
}
