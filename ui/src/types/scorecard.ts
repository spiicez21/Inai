/**
 * Mirrors `inai/eval/scorecard.py` field-for-field. Change one, change the other.
 *
 * All monetary values are INTEGER PAISE, never rupees and never floats — same rule as the
 * backend. Convert only at render, with `fmtPaise` in `lib/format.ts`.
 */

export const SCORECARD_VERSION = 1

export type MatchTierId =
  | 't0_exact'
  | 't1_deterministic'
  | 't2_fuzzy'
  | 't3_structural'
  | 't4_adversarial'

export type ArmId = 'agent' | 'control' | 'pure_holdout'

export type ExceptionClassId =
  | 'UNAPPLIED_CASH'
  | 'GENUINELY_UNPAID'
  | 'SHORT_SETTLEMENT'
  | 'MISSING_REFUND_REVERSAL'
  | 'UNSETTLED_CAPTURE'
  | 'PARTIAL_PAYMENT'
  | 'FEE_TAX_VARIANCE'
  | 'DUPLICATE_PAYMENT'
  | 'TIMING_DIFFERENCE'
  | 'DISPUTE_HOLD'
  | 'UNRESOLVED'

export interface RunMeta {
  run_id: string
  config_name: string
  seed: number
  config_hash: string
  scorecard_version: number
  started_at: string
  finished_at: string
  n_records: number
  duration_seconds: number
  records_per_second: number
  hardware: string
  inai_version: string
  llm_mode: 'replay' | 'live' | 'off'
}

export interface TierResult {
  tier: MatchTierId
  eligible: number
  matched: number
  match_rate_pct: number
  target_pct_low: number
  target_pct_high: number
  /** What reporting this tier actually proves. T0's is "Nothing. Say so on the slide." */
  proves: string
}

export interface ReconMetrics {
  tiers: TierResult[]
  auto_match_rate_pct: number
  overall_match_rate_pct: number
  exception_rate_pct: number
  residual_explained_pct: number
  total_residual_paise: number
  attributed_residual_paise: number
}

export interface ArmResult {
  arm: ArmId
  n_accounts: number
  at_risk_paise: number
  recovered_paise: number
  gross_recovery_rate_pct: number
  contacts_made: number
  retries_attempted: number
  cost_incurred_paise: number
}

export interface ConfidenceInterval {
  point: number
  low: number
  high: number
  method: 'two_proportion_z' | 'bootstrap_10k'
  /** If true, the UI says so in words. An interval that crosses zero is not a result. */
  crosses_zero: boolean
}

export interface RecoveryMetrics {
  arms: ArmResult[]
  self_cure_rate_pct: number
  baseline_rate_pct: number
  agent_rate_pct: number
  incremental_vs_baseline_paise: number
  lift_pct: number
  rate_difference_ci: ConfidenceInterval
  incremental_paise_ci: ConfidenceInterval
  cost_per_100_recovered_paise: number
  mde_pp: number
  oracle_gap_pct: number | null
}

export interface BridgeMetrics {
  false_dunning_prevented_n: number
  false_dunning_prevented_paise: number
  rails_leakage_recovered_paise: number
  rails_leakage_by_class: Partial<Record<ExceptionClassId, number>>
  futile_retries_avoided: number
  futile_retry_savings_paise: number
}

export interface ExceptionBucket {
  cls: ExceptionClassId
  count: number
  amount_paise: number
  pct_of_batch: number
  routed_action_counts: Record<string, number>
}

export interface PolicyBlock {
  rule_id: string
  rule_text: string
  blocked_count: number
  amount_affected_paise: number
}

export interface Scorecard {
  /** Set whenever any figure on the scorecard is not yet produced by real code.
   *  A dedicated field, not a magic prefix in `limitations` — a warning that a rename can
   *  silently switch off is not a warning. */
  provenance_warning: string | null
  meta: RunMeta
  recon: ReconMetrics
  recovery: RecoveryMetrics
  bridge: BridgeMetrics
  exceptions: ExceptionBucket[]
  unresolved_count: number
  policy_blocks: PolicyBlock[]
  limitations: string[]
}

/** One row of `exceptions.parquet` / `exceptions.csv`. */
export interface ExceptionRow {
  exception_id: string
  cls: ExceptionClassId
  tier: MatchTierId
  ledger_ref: string
  settlement_ref: string
  bank_ref: string
  amount_paise: number
  machine_reason: string
  human_reason: string
  routed_action: string
}
