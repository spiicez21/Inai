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
 * POL-RECON-001 is highlighted because it is the rule that only exists because Stage 1
 * exists — money arrived, so no dunning may fire, regardless of what the ledger says.
 */
export function PolicyPanel({ blocks }: { blocks: PolicyBlock[] }) {
  const sorted = [...blocks].sort((a, b) => b.blocked_count - a.blocked_count)

  return (
    <Card>
      <PanelHeader
        title="Actions blocked, by rule"
        note="Blocked actions are logged, never silently dropped. Each verdict carries a rule ID, the rule text, and a remediation."
        right={<ShieldCheck size={15} className="text-base-600" />}
      />
      <div className="hairline">
        {sorted.length === 0 ? (
          <Empty>No actions blocked in this run.</Empty>
        ) : (
          <ul>
            {sorted.map((b) => {
              const isBridgeRule = b.rule_id === 'POL-RECON-001'
              return (
                <li
                  key={b.rule_id}
                  className="border-base-850 flex items-start gap-3 border-b px-4 py-2.5 last:border-0"
                >
                  <span
                    className={`num shrink-0 rounded px-1.5 py-0.5 text-[0.6875rem] ring-1 ring-inset ${
                      isBridgeRule
                        ? 'bg-accent/12 text-accent ring-accent/30'
                        : 'bg-base-850 text-base-400 ring-base-800'
                    }`}
                  >
                    {b.rule_id}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-base-300 text-xs leading-snug">{b.rule_text}</p>
                    {isBridgeRule ? (
                      <p className="text-accent/70 mt-1 text-[0.6875rem] leading-snug">
                        This rule only exists because Stage 1 exists. Point at it in the demo.
                      </p>
                    ) : null}
                  </div>
                  <div className="shrink-0 text-right">
                    <div className="num text-blocked text-xs">{fmtCount(b.blocked_count)}</div>
                    <div className="num text-base-600 text-[0.625rem]">
                      {fmtPaiseCompact(b.amount_affected_paise)}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </Card>
  )
}
