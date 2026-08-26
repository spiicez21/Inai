import { EXCEPTION_LABEL, fmtCount, fmtPaise, fmtPaiseCompact } from '@/lib/format'
import type { BridgeMetrics } from '@/types/scorecard'
import { ArrowRight, Ban, Coins, PhoneOff } from 'lucide-react'
import { Card, Figure, PanelHeader } from './primitives'

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
    <Card>
      <PanelHeader
        title="The bridge"
        note="Track 03 revenue metrics produced by a Track 04 capability. Remove either half and these numbers cannot be computed at all."
        right={
          <span
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 font-mono text-[0.6875rem]"
            style={{ background: 'var(--color-accent-soft)', color: 'var(--color-accent-fg)' }}
          >
            recon <ArrowRight size={11} /> recovery
          </span>
        }
      />

      {/* Three tiles, not four. The leakage-by-class breakdown moved to a single line
          underneath — it is supporting detail for one of the three, not a peer of them. */}
      <div className="grid gap-4 px-6 pt-2 pb-5 md:grid-cols-3">
        <Tile
          icon={<PhoneOff size={15} />}
          label="False dunning prevented"
          figure={fmtCount(bridge.false_dunning_prevented_n)}
          unit="accounts"
          note={
            <>
              chased by control, <strong className="font-semibold">already paid</strong>
            </>
          }
          foot={`${fmtPaise(bridge.false_dunning_prevented_paise)} in contact cost and modelled churn`}
          bg="var(--color-accent)"
          fg="var(--color-on-accent)"
          filled
        />
        <Tile
          icon={<Coins size={15} />}
          label="Rails leakage recovered"
          figure={fmtPaiseCompact(bridge.rails_leakage_recovered_paise)}
          note="invisible without reconciliation"
          foot={
            leakage.length
              ? leakage
                  .slice(0, 3)
                  .map(([cls, amt]) => `${EXCEPTION_LABEL[cls] ?? cls} ${fmtPaiseCompact(amt!)}`)
                  .join('  ·  ')
              : 'none found in this batch'
          }
          bg="var(--color-lime)"
          fg="var(--color-on-lime)"
          filled
        />
        <Tile
          icon={<Ban size={15} />}
          label="Futile retries avoided"
          figure={fmtCount(bridge.futile_retries_avoided)}
          unit="retries"
          note="against causes that can never succeed"
          foot={`${fmtPaise(bridge.futile_retry_savings_paise)} in bounce fees not incurred`}
        />
      </div>
    </Card>
  )
}

function Tile({
  icon,
  label,
  figure,
  unit,
  note,
  foot,
  bg,
  fg,
  filled = false,
}: {
  icon: React.ReactNode
  label: string
  figure: string
  unit?: string
  note: React.ReactNode
  /** The supporting rupee figure. Deliberately quieter than `note` — it is evidence for
   *  the headline, not a second headline. */
  foot?: React.ReactNode
  bg?: string
  fg?: string
  filled?: boolean
}) {
  const muted = filled ? fg : 'var(--color-fg-subtle)'
  return (
    <div
      className="flex flex-col rounded-[--radius-tile] p-5"
      style={{ background: filled ? bg : 'var(--color-inset)' }}
    >
      <div
        className="flex items-center gap-1.5 text-[0.6875rem] font-medium tracking-[0.06em] uppercase"
        style={{ color: muted, opacity: filled ? 0.8 : 1 }}
      >
        {icon}
        <span className="truncate">{label}</span>
      </div>

      <div className="mt-4 flex items-baseline gap-1.5">
        <Figure
          value={figure}
          className="text-[2rem] leading-none"
          tone={filled ? fg : 'var(--color-fg-strong)'}
        />
        {unit ? (
          <span className="text-xs" style={{ color: muted, opacity: filled ? 0.7 : 1 }}>
            {unit}
          </span>
        ) : null}
      </div>

      <p className="mt-2 text-xs leading-snug" style={{ color: muted, opacity: filled ? 0.9 : 1 }}>
        {note}
      </p>

      {foot ? (
        <p
          className="mt-auto pt-4 text-[0.6875rem] leading-snug"
          style={{ color: muted, opacity: filled ? 0.65 : 0.8 }}
        >
          {foot}
        </p>
      ) : null}
    </div>
  )
}
