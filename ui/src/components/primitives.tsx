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
    <div className="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
      <div className="min-w-0">
        <h2
          className="text-[0.9375rem] leading-tight font-semibold"
          style={{ color: 'var(--color-fg-strong)' }}
        >
          {title}
        </h2>
        {note ? (
          <p className="mt-1 text-xs leading-relaxed" style={{ color: 'var(--color-fg-subtle)' }}>
            {note}
          </p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  )
}

const TIER_VAR: Record<MatchTierId, string> = {
  t0_exact: 'tier-0',
  t1_deterministic: 'tier-1',
  t2_fuzzy: 'tier-2',
  t3_structural: 'tier-3',
  t4_adversarial: 'tier-4',
}

/** Single-hue ramp, so "further down the alphabet = harder" reads without a legend. */
export function TierBadge({ tier, className }: { tier: MatchTierId; className?: string }) {
  const v = TIER_VAR[tier]
  return (
    <span
      className={cn(
        'num inline-flex items-center rounded-md px-1.5 py-0.5 text-[0.6875rem] font-medium',
        className,
      )}
      style={{
        background: `color-mix(in oklab, var(--color-${v}) 22%, transparent)`,
        // Only 55% of the tier hue: the pale end of the ramp (T0/T1) is a light green, and
        // at 80% the label washed out against its own tint. The ramp still reads because
        // the background tint carries it.
        color: `color-mix(in oklab, var(--color-${v}) 55%, var(--color-fg-strong))`,
      }}
    >
      {TIER_SHORT[tier]}
    </span>
  )
}

type Tone = 'matched' | 'exception' | 'blocked' | 'suppressed' | 'accent' | 'lime' | 'neutral'

const TONE_BG: Record<Tone, string> = {
  matched: 'var(--color-matched-soft)',
  exception: 'var(--color-exception-soft)',
  blocked: 'var(--color-blocked-soft)',
  suppressed: 'var(--color-inset)',
  accent: 'var(--color-accent-soft)',
  lime: 'var(--color-lime-soft)',
  neutral: 'var(--color-inset)',
}

const TONE_FG: Record<Tone, string> = {
  matched: 'var(--color-matched)',
  exception: 'var(--color-exception)',
  blocked: 'var(--color-blocked)',
  suppressed: 'var(--color-suppressed)',
  accent: 'var(--color-accent-fg)',
  lime: 'var(--color-lime-fg)',
  neutral: 'var(--color-fg-muted)',
}

/** The reference's pill: soft tinted background, icon optional, tight. */
export function Badge({
  tone = 'neutral',
  children,
  className,
  title,
  icon,
}: {
  tone?: Tone
  children: ReactNode
  className?: string
  title?: string
  icon?: ReactNode
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[0.6875rem] font-medium',
        className,
      )}
      style={{ background: TONE_BG[tone], color: TONE_FG[tone] }}
    >
      {icon}
      {children}
    </span>
  )
}

/**
 * A big figure with receding decimals — the reference's signature treatment. The eye lands
 * on the magnitude, and the paise are still there for anyone checking the arithmetic.
 */
export function Figure({
  value,
  className,
  tone,
}: {
  value: string
  className?: string
  tone?: string
}) {
  const m = value.match(/^(.*?)([.,]\d{2})$/)
  return (
    <span className={cn('figure', className)} style={tone ? { color: tone } : undefined}>
      {m ? (
        <>
          {m[1]}
          <span className="figure-dec text-[0.62em]">{m[2]}</span>
        </>
      ) : (
        value
      )}
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
  const color =
    tone === 'neutral' || tone === 'suppressed' ? 'var(--color-fg-strong)' : TONE_FG[tone]
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <span className="eyebrow truncate">{label}</span>
      <span
        className={cn('text-[1.5rem] leading-none font-semibold', mono && 'tracking-tight')}
        style={{ color, fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </span>
      {sub ? (
        <span className="text-xs leading-snug" style={{ color: 'var(--color-fg-subtle)' }}>
          {sub}
        </span>
      ) : null}
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
  return (
    <div
      className="relative h-2 w-full overflow-hidden rounded-full"
      style={{ background: 'var(--color-inset)' }}
    >
      {target ? (
        <div
          className="absolute inset-y-0"
          style={{
            left: `${target[0]}%`,
            width: `${Math.max(target[1] - target[0], 0.5)}%`,
            background: 'var(--color-border)',
          }}
          title={`target ${target[0]}–${target[1]}%`}
        />
      ) : null}
      <div
        className="absolute inset-y-0 left-0 rounded-full"
        style={{ width: `${Math.min(Math.max(value, 0), 100)}%`, background: TONE_FG[tone] }}
      />
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex h-full min-h-32 items-center justify-center px-6 py-10 text-center text-sm"
      style={{ color: 'var(--color-fg-subtle)' }}
    >
      {children}
    </div>
  )
}
