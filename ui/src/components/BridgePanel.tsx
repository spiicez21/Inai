import { EXCEPTION_LABEL, fmtCount, fmtPaise, fmtPaiseCompact } from '@/lib/format'
import type { BridgeMetrics } from '@/types/scorecard'
import { ArrowRight, Ban, Coins, PhoneOff } from 'lucide-react'
import { Card, PanelHeader, Stat } from './primitives'

/**
 * INAI_SPEC.md §9.4 — the two metrics only INAI can report, and §12 step 5, the moment the
 * submission wins or loses.
 *
 * A pure recovery agent cannot compute false-dunning-prevented: it does not know the money
 * arrived. A pure reconciliation agent cannot compute it either: it has no dunning queue to
 * cancel. The number exists only where both halves run over the same batch.
 */
export function BridgePanel({ bridge }: { bridge: BridgeMetrics }) {
  const leakage = Object.entries(bridge.rails_leakage_by_class).sort((a, b) => b[1]! - a[1]!)

  return (
    <Card className="ring-accent/20 ring-1">
      <PanelHeader
        title="The bridge"
        note="Track 03 revenue metrics produced by a Track 04 capability. Remove either half and these numbers cannot be computed at all."
        right={
          <span className="text-accent/80 flex items-center gap-1.5 font-mono text-[0.6875rem]">
            recon <ArrowRight size={11} /> recovery
          </span>
        }
      />

      <div className="hairline grid gap-5 px-4 py-4 sm:grid-cols-2">
        <div className="flex gap-3">
          <PhoneOff size={16} className="text-matched mt-1 shrink-0" />
          <Stat
            label="False dunning prevented"
            tone="matched"
            value={fmtCount(bridge.false_dunning_prevented_n)}
            sub={
              <>
                accounts the control arm chased that had{' '}
                <span className="text-base-300">already paid</span> ·{' '}
                <span className="num">{fmtPaise(bridge.false_dunning_prevented_paise)}</span> in
                contact cost and modelled churn risk
              </>
            }
          />
        </div>

        <div className="flex gap-3">
          <Coins size={16} className="text-accent mt-1 shrink-0" />
          <Stat
            label="Rails leakage recovered"
            tone="accent"
            value={fmtPaiseCompact(bridge.rails_leakage_recovered_paise)}
            sub="revenue recovery that is literally invisible without reconciliation — short settlements, unreversed refunds, unsettled captures, adverse fee variance"
          />
        </div>

        <div className="flex gap-3">
          <Ban size={16} className="text-exception mt-1 shrink-0" />
          <Stat
            label="Futile retries avoided"
            tone="exception"
            value={fmtCount(bridge.futile_retries_avoided)}
            sub={
              <>
                retries against causes that can never succeed ·{' '}
                <span className="num">{fmtPaise(bridge.futile_retry_savings_paise)}</span> in bounce
                fees not incurred
              </>
            }
          />
        </div>

        <div className="min-w-0">
          <span className="eyebrow">Leakage by class</span>
          <ul className="mt-2 space-y-1">
            {leakage.length === 0 ? (
              <li className="text-base-600 text-xs">none found in this batch</li>
            ) : (
              leakage.map(([cls, amount]) => (
                <li key={cls} className="flex items-baseline justify-between gap-3 text-xs">
                  <span className="text-base-400 truncate">{EXCEPTION_LABEL[cls] ?? cls}</span>
                  <span className="num text-base-200 shrink-0">{fmtPaiseCompact(amount!)}</span>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </Card>
  )
}
