import { cn } from '@/lib/cn'
import { TIER_SHORT } from '@/lib/format'
import type { MatchTierId } from '@/types/scorecard'
import type { ReactNode } from 'react'

export function Card({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('card', className)} {...rest}>
      {children}
    </div>
  )
}

export function PanelHeader({
  title,
  note,
  right,
}: {
  title: string
  /** The caveat that belongs next to the number, not three slides later. */
  note?: ReactNode
  right?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 pt-3.5 pb-3">
      <div className="min-w-0">
        <h2 className="text-base-100 text-[0.9375rem] leading-tight font-medium">{title}</h2>
        {note ? <p className="text-base-500 mt-1 text-xs leading-relaxed">{note}</p> : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  )
}

const TIER_CLASS: Record<MatchTierId, string> = {
  t0_exact: 'bg-tier-0/15 text-tier-0 ring-tier-0/25',
  t1_deterministic: 'bg-tier-1/15 text-tier-1 ring-tier-1/25',
  t2_fuzzy: 'bg-tier-2/20 text-tier-2 ring-tier-2/30',
  t3_structural: 'bg-tier-3/25 text-tier-3 ring-tier-3/35',
  t4_adversarial: 'bg-tier-4/30 text-tier-4 ring-tier-4/40',
}

/** Single-hue ramp, so "further down the alphabet = harder" reads without a legend. */
export function TierBadge({ tier, className }: { tier: MatchTierId; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[0.6875rem] font-medium ring-1 ring-inset',
        TIER_CLASS[tier],
        className,
      )}
    >
      {TIER_SHORT[tier]}
    </span>
  )
}

type Tone = 'matched' | 'exception' | 'blocked' | 'suppressed' | 'accent' | 'neutral'

const TONE_CLASS: Record<Tone, string> = {
  matched: 'bg-matched/12 text-matched ring-matched/25',
  exception: 'bg-exception/12 text-exception ring-exception/25',
  blocked: 'bg-blocked/12 text-blocked ring-blocked/25',
  suppressed: 'bg-base-800 text-suppressed ring-base-700',
  accent: 'bg-accent/12 text-accent ring-accent/25',
  neutral: 'bg-base-800 text-base-300 ring-base-700',
}

export function Badge({
  tone = 'neutral',
  children,
  className,
  title,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  title?: string
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-[0.6875rem] font-medium ring-1 ring-inset',
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

/** A headline number. `sub` is where the honesty goes — the CI, the caveat, the denominator. */
export function Stat({
  label,
  value,
  sub,
  tone = 'neutral',
  mono = true,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: Tone
  mono?: boolean
}) {
  const valueTone =
    tone === 'matched'
      ? 'text-matched'
      : tone === 'exception'
        ? 'text-exception'
        : tone === 'blocked'
          ? 'text-blocked'
          : tone === 'accent'
            ? 'text-accent'
            : 'text-base-50'
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="eyebrow truncate">{label}</span>
      <span
        className={cn(
          'text-[1.375rem] leading-none font-semibold',
          mono && 'num tracking-tight',
          valueTone,
        )}
      >
        {value}
      </span>
      {sub ? <span className="text-base-500 text-xs leading-snug">{sub}</span> : null}
    </div>
  )
}

/** Horizontal meter. `target` draws the band we said we were aiming for, so a tier that
 *  lands below its own target is visibly below it rather than merely a smaller number. */
export function Meter({
  value,
  target,
  tone = 'accent',
}: {
  value: number
  target?: [number, number]
  tone?: Tone
}) {
  const barTone =
    tone === 'matched'
      ? 'bg-matched'
      : tone === 'exception'
        ? 'bg-exception'
        : tone === 'blocked'
          ? 'bg-blocked'
          : 'bg-accent'
  return (
    <div className="bg-base-850 relative h-1.5 w-full overflow-hidden rounded-full">
      {target ? (
        <div
          className="bg-base-700/70 absolute inset-y-0"
          style={{ left: `${target[0]}%`, width: `${Math.max(target[1] - target[0], 0.5)}%` }}
          title={`target ${target[0]}–${target[1]}%`}
        />
      ) : null}
      <div
        className={cn('absolute inset-y-0 left-0 rounded-full', barTone)}
        style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
      />
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="text-base-500 flex h-full min-h-32 items-center justify-center px-6 py-10 text-center text-sm">
      {children}
    </div>
  )
}
