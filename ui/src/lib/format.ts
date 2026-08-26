/**
 * Rendering money. The twin of `inai/money.py`.
 *
 * Indian digit grouping is not cosmetic here: ₹12,34,567 vs ₹1,234,567 is the difference
 * between a tool built for this market and a tool that was not.
 */

const INR = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const INR_COMPACT = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  notation: 'compact',
  maximumFractionDigits: 2,
})

const COUNT = new Intl.NumberFormat('en-IN')

/** Paise (integer) -> "₹12,34,567.89". The ONLY place paise become rupees. */
export function fmtPaise(paise: number): string {
  return INR.format(paise / 100)
}

/** Paise -> "₹12.35L" / "₹1.2Cr". For headline tiles where precision would crowd out scale. */
export function fmtPaiseCompact(paise: number): string {
  return INR_COMPACT.format(paise / 100)
}

/** Indian grouping for plain counts too — 12,34,567 records, not 1,234,567. */
export function fmtCount(n: number): string {
  return COUNT.format(n)
}

export function fmtPct(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`
}

/** Signed percentage points, for rate differences. "+11.5 pp" reads unambiguously. */
export function fmtPp(value: number, digits = 1): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)} pp`
}

export function fmtCI(low: number, high: number, digits = 1): string {
  return `[${fmtPp(low, digits)}, ${fmtPp(high, digits)}]`
}

export function fmtThroughput(recordsPerSecond: number): string {
  return `${COUNT.format(Math.round(recordsPerSecond))} rec/s`
}

export function fmtDuration(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(2)} s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

/** Human labels. The full names are unreadable in a dense table. */
export const TIER_LABEL = {
  t0_exact: 'T0 · exact',
  t1_deterministic: 'T1 · deterministic',
  t2_fuzzy: 'T2 · fuzzy',
  t3_structural: 'T3 · structural',
  t4_adversarial: 'T4 · adversarial',
} as const

export const TIER_SHORT = {
  t0_exact: 'T0',
  t1_deterministic: 'T1',
  t2_fuzzy: 'T2',
  t3_structural: 'T3',
  t4_adversarial: 'T4',
} as const

export const ARM_LABEL = {
  agent: 'Agent',
  control: 'Control',
  pure_holdout: 'Pure holdout',
} as const

export const ARM_NOTE = {
  agent: 'Full pipeline',
  control: 'Naive baseline — no reconciliation',
  pure_holdout: 'No action at all — measures true self-cure',
} as const

export const EXCEPTION_LABEL: Record<string, string> = {
  UNAPPLIED_CASH: 'Unapplied cash',
  GENUINELY_UNPAID: 'Genuinely unpaid',
  SHORT_SETTLEMENT: 'Short settlement',
  MISSING_REFUND_REVERSAL: 'Missing refund reversal',
  UNSETTLED_CAPTURE: 'Unsettled capture',
  PARTIAL_PAYMENT: 'Partial payment',
  FEE_TAX_VARIANCE: 'Fee / tax variance',
  DUPLICATE_PAYMENT: 'Duplicate payment',
  TIMING_DIFFERENCE: 'Timing difference',
  DISPUTE_HOLD: 'Dispute hold',
  UNRESOLVED: 'Unresolved',
}

/** One line each, from INAI_SPEC.md §2. Shown on hover in the exception table. */
export const EXCEPTION_REALITY: Record<string, string> = {
  UNAPPLIED_CASH: 'Paid, unmatched — auto-apply and cancel scheduled dunning',
  GENUINELY_UNPAID: 'No payment exists — recovery ladder',
  SHORT_SETTLEMENT: 'Gateway paid less than computed — raise adjustment query',
  MISSING_REFUND_REVERSAL: 'Refund debited, never reversed — claim it',
  UNSETTLED_CAPTURE: 'Captured, never settled — chase settlement',
  PARTIAL_PAYMENT: 'Underpaid — chase the balance only',
  FEE_TAX_VARIANCE: 'MDR/GST/TCS computed ≠ deducted — dispute or accept within tolerance',
  DUPLICATE_PAYMENT: 'Paid twice — credit note or refund',
  TIMING_DIFFERENCE: 'Will settle T+n — suppress action, revisit',
  DISPUTE_HOLD: 'Chargeback in flight — freeze, human queue',
  UNRESOLVED: 'Honest gap — human queue, displayed not hidden',
}

/** Rails leakage is revenue recovery that is invisible without reconciliation (§9.4). */
export const RAILS_LEAKAGE_CLASSES = new Set([
  'SHORT_SETTLEMENT',
  'MISSING_REFUND_REVERSAL',
  'UNSETTLED_CAPTURE',
  'FEE_TAX_VARIANCE',
])
