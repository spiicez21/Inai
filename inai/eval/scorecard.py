"""The scorecard. INAI_SPEC.md §9.

This module is the contract between the pipeline and the UI. `ui/src/types/scorecard.ts`
mirrors it field-for-field — change one, change the other.

The harness IS the product (§0.4). Everything here is reported, including the parts that
make INAI look worse: the tier where it loses, the confidence interval that crosses zero,
the records it could not resolve.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from inai.schema import Arm, ExceptionClass, MatchTier

SCORECARD_VERSION = 1


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RunMeta(Frozen):
    """Printed on the face of the scorecard. "Re-run it yourself." (§12.8)"""

    run_id: str
    config_name: str
    seed: int
    config_hash: str
    scorecard_version: int = SCORECARD_VERSION
    started_at: datetime
    finished_at: datetime
    n_records: int
    duration_seconds: float
    records_per_second: float
    hardware: str  # throughput without hardware is not a claim (§9.2)
    inai_version: str
    llm_mode: Literal["replay", "live", "off"]


class TierResult(Frozen):
    """§9.2 — reported per tier, NEVER blended into one headline number."""

    tier: MatchTier
    eligible: int
    matched: int
    match_rate_pct: float
    target_pct_low: float
    target_pct_high: float
    #: What reporting this tier actually proves. T0 gets "Nothing. Say so on the slide."
    proves: str


class ReconMetrics(Frozen):
    tiers: list[TierResult]
    auto_match_rate_pct: float  # T0..T2 / total — the vendor-comparable number
    overall_match_rate_pct: float
    exception_rate_pct: float  # target 5-12%
    residual_explained_pct: float
    total_residual_paise: int
    attributed_residual_paise: int


class ArmResult(Frozen):
    arm: Arm
    n_accounts: int
    at_risk_paise: int
    recovered_paise: int
    gross_recovery_rate_pct: float
    contacts_made: int
    retries_attempted: int
    cost_incurred_paise: int


class ConfidenceInterval(Frozen):
    """§9.5 — if it crosses zero, say so on the slide."""

    point: float
    low: float
    high: float
    method: Literal["two_proportion_z", "bootstrap_10k"]
    crosses_zero: bool


class RecoveryMetrics(Frozen):
    arms: list[ArmResult]
    self_cure_rate_pct: float  # PURE_HOLDOUT — most of any gross number was never earned
    baseline_rate_pct: float  # CONTROL
    agent_rate_pct: float
    incremental_vs_baseline_paise: int  # <- HEADLINE
    lift_pct: float
    rate_difference_ci: ConfidenceInterval
    incremental_paise_ci: ConfidenceInterval
    cost_per_100_recovered_paise: int
    mde_pp: float  # minimum detectable effect, percentage points
    oracle_gap_pct: float | None = None  # free, because we own the labels (DATA.md §5.3)


class BridgeMetrics(Frozen):
    """§9.4 — the two metrics only INAI can report.

    A pure recovery agent cannot compute `false_dunning_prevented` (it does not know the
    money arrived). A pure recon agent cannot compute it (it has no dunning queue to
    cancel). This is the proof that the two tracks are one loop.
    """

    false_dunning_prevented_n: int
    false_dunning_prevented_paise: int
    rails_leakage_recovered_paise: int
    rails_leakage_by_class: dict[ExceptionClass, int]
    futile_retries_avoided: int
    futile_retry_savings_paise: int


class ExceptionBucket(Frozen):
    cls: ExceptionClass
    count: int
    amount_paise: int
    pct_of_batch: float
    routed_action_counts: dict[str, int] = Field(default_factory=dict)


class PolicyBlock(Frozen):
    """Blocked actions are logged, never silently dropped (§8.5)."""

    rule_id: str
    rule_text: str
    blocked_count: int
    amount_affected_paise: int


class Scorecard(Frozen):
    meta: RunMeta
    recon: ReconMetrics
    recovery: RecoveryMetrics
    bridge: BridgeMetrics
    exceptions: list[ExceptionBucket]
    unresolved_count: int  # the honest gap, displayed by default (§9.6)
    policy_blocks: list[PolicyBlock]
    limitations: list[str] = Field(default_factory=list)
