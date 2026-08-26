"""Score the matcher against ground truth. INAI_SPEC.md §9.2.

    match_rate(tier)       = matched(tier) / eligible(tier)      # NEVER blended
    auto_match_rate        = matched(T0..T2) / total             # comparable to vendor claims
    residual_explained_pct = Σ|residual| attributed / Σ|residual|
    exception_rate         = exceptions / total                  # target 5-12%

**This is the only module where the matcher's output and the answers meet.** `eval/**` may
import `sim.truth`; `match/**` may not. The tier a record is *scored under* comes from
truth (the hardest corruption operator that fired on it), not from the tier the matcher
happened to succeed at — otherwise the denominator would be chosen by the thing being
measured, and every rate would be circular.
"""

from __future__ import annotations

from inai.eval.scorecard import ReconMetrics, TierResult
from inai.match.types import ReconOutput
from inai.money import pct
from inai.schema import TIER_ORDER, MatchTier
from inai.sim.truth import TruthLink

#: Targets from DATA.md §5.2, and what reporting each tier actually proves.
TIER_TARGETS: dict[MatchTier, tuple[float, float]] = {
    MatchTier.T0_EXACT: (99.0, 100.0),
    MatchTier.T1_DETERMINISTIC: (97.0, 100.0),
    MatchTier.T2_FUZZY: (80.0, 90.0),
    MatchTier.T3_STRUCTURAL: (60.0, 75.0),
    MatchTier.T4_ADVERSARIAL: (0.0, 50.0),
}

TIER_PROVES: dict[MatchTier, str] = {
    MatchTier.T0_EXACT: "Nothing. Say so on the slide.",
    MatchTier.T1_DETERMINISTIC: "Baseline competence.",
    MatchTier.T2_FUZZY: "The real score.",
    MatchTier.T3_STRUCTURAL: "Genuine engineering.",
    MatchTier.T4_ADVERSARIAL: "Intellectual honesty.",
}


def score(output: ReconOutput, truth: list[TruthLink]) -> ReconMetrics:
    """Tiered match rates, never blended into one headline number."""
    tier_of = {t.ledger_ref: t.difficulty_tier for t in truth}
    matched_refs = {m.ledger_ref for m in output.matched}

    eligible: dict[MatchTier, int] = dict.fromkeys(MatchTier, 0)
    matched: dict[MatchTier, int] = dict.fromkeys(MatchTier, 0)

    for result in output.matches:
        # Scored under the tier the RECORD is, not the tier the matcher reached.
        tier = tier_of.get(result.ledger_ref, MatchTier.T0_EXACT)
        eligible[tier] += 1
        if result.ledger_ref in matched_refs:
            matched[tier] += 1

    total = len(output.matches)
    auto = sum(
        matched[t] for t in (MatchTier.T0_EXACT, MatchTier.T1_DETERMINISTIC, MatchTier.T2_FUZZY)
    )
    total_matched = sum(matched.values())

    tiers = [
        TierResult(
            tier=tier,
            eligible=eligible[tier],
            matched=matched[tier],
            match_rate_pct=round(pct(matched[tier], eligible[tier]), 2),
            target_pct_low=TIER_TARGETS[tier][0],
            target_pct_high=TIER_TARGETS[tier][1],
            proves=TIER_PROVES[tier],
        )
        for tier in TIER_ORDER
    ]

    total_residual = int(output.total_residual_paise)
    attributed = int(output.attributed_residual_paise)

    return ReconMetrics(
        tiers=tiers,
        auto_match_rate_pct=round(pct(auto, total), 2),
        overall_match_rate_pct=round(pct(total_matched, total), 2),
        exception_rate_pct=round(pct(total - total_matched, total), 2),
        residual_explained_pct=round(pct(attributed, total_residual), 2),
        total_residual_paise=total_residual,
        attributed_residual_paise=attributed,
    )


def oracle_gap_inputs(output: ReconOutput, truth: list[TruthLink]) -> tuple[int, int]:
    """`(matched, recoverable_by_perfect_policy)` — free, because we own the labels.

    Rare in hackathon submissions and costs nothing (DATA.md §5.3). Consumed by phase 6.
    """
    matched_refs = {m.ledger_ref for m in output.matched}
    perfect = sum(1 for t in truth if t.recoverable_by_perfect_policy)
    return len(matched_refs), perfect
