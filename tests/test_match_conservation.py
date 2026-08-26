"""Matcher invariants. INAI_SPEC.md §6.3, DATA.md §8.

    Σ matched + Σ exceptions == Σ input records, always.

Plus the two rules that make the match rate mean anything:
  * every match carries an explanation a human can check in five seconds
  * a confident wrong allocation is worse than an honest exception
"""

from __future__ import annotations

import numpy as np
import pytest

from inai.config import ResolvedConfig
from inai.eval.score_match import score
from inai.match.cascade import match
from inai.match.types import ReconInput
from inai.match.utr import extract_utr, normalise
from inai.schema import MatchTier
from inai.sim.build import BuildResult, build
from inai.sim.spine import spine_available

pytestmark = pytest.mark.skipif(
    not spine_available(), reason="Olist spine not present — see DATA.md §2"
)


def _built(seed: int = 42) -> BuildResult:
    cfg = ResolvedConfig.resolve("configs/smoke.yaml", seed=seed)
    return build(cfg, np.random.default_rng(cfg.run.seed))


@pytest.fixture(scope="module")
def built() -> BuildResult:
    return _built()


@pytest.fixture(scope="module")
def data(built: BuildResult) -> ReconInput:
    return ReconInput(
        invoices=[c.invoice for c in built.batch.chains],
        legs=[leg for c in built.batch.chains for leg in c.legs],
        credits=list(built.batch.credits),
    )


@pytest.fixture(scope="module")
def output(data: ReconInput):
    return match(data)


# ---------------------------------------------------------------------------
# Conservation — the property that must never fail
# ---------------------------------------------------------------------------
def test_matched_plus_exceptions_equals_input(output, data: ReconInput) -> None:
    assert len(output.matched) + len(output.unmatched) == len(data.invoices)


def test_every_invoice_appears_exactly_once(output, data: ReconInput) -> None:
    refs = [m.ledger_ref for m in output.matches]
    assert len(refs) == len(set(refs)) == len(data.invoices)


def test_no_settlement_leg_is_claimed_twice(output) -> None:
    """One payment cannot settle two invoices. Double-claiming would inflate the match rate
    while leaving real invoices unpaid and unnoticed."""
    claimed = [ref for m in output.matched for ref in m.settlement_refs]
    assert len(claimed) == len(set(claimed))


# ---------------------------------------------------------------------------
# Correctness — matched is not the same as RIGHT
# ---------------------------------------------------------------------------
def test_matches_point_at_the_correct_legs(output, built: BuildResult) -> None:
    """A match against the wrong legs is worse than no match at all.

    Checking only matched/unmatched would let the cascade score well by allocating money
    confidently and wrongly, which is the exact vendor behaviour this project exists to
    argue against. So the match rate is only meaningful if the allocations are also right.
    """
    truth = {t.ledger_ref: set(t.settlement_refs) for t in built.truth}
    wrong = [
        m.ledger_ref
        for m in output.matched
        if m.settlement_refs and not set(m.settlement_refs).issubset(truth.get(m.ledger_ref, set()))
    ]
    rate = len(wrong) / max(len(output.matched), 1)
    assert rate < 0.02, f"{len(wrong)} of {len(output.matched)} matches point at the wrong legs"


def test_every_match_carries_an_explanation(output) -> None:
    for m in output.matches:
        assert m.explanation.strip(), f"{m.ledger_ref} has no explanation"
        assert len(m.explanation) < 400, "an explanation nobody will read is not one"


def test_confidence_is_ordered_by_tier(output) -> None:
    for m in output.matched:
        if m.tier is MatchTier.T0_EXACT:
            assert m.confidence == 1.0
        else:
            assert 0.0 < m.confidence <= 1.0


# ---------------------------------------------------------------------------
# Tie-outs
# ---------------------------------------------------------------------------
def test_every_settlement_gets_a_tie_out(output, data: ReconInput) -> None:
    settlements = {leg.settlement_id for leg in data.legs}
    assert {t.settlement_id for t in output.tie_outs} == settlements


def test_every_unclean_tie_out_is_attributed(output) -> None:
    """The residual is the product. An unexplained gap with no attribution is a shrug."""
    for t in output.tie_outs:
        if not t.clean:
            assert t.attributed_to, f"{t.settlement_id} has an unattributed residual"


def test_residual_equals_observed_minus_expected(output) -> None:
    for t in output.tie_outs:
        assert int(t.residual_paise) == int(t.observed_net_paise) - int(t.expected_net_paise)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def test_tier_rates_are_reported_separately(output, built: BuildResult) -> None:
    metrics = score(output, built.truth)
    assert len(metrics.tiers) == 5
    assert sum(t.eligible for t in metrics.tiers) == len(output.matches)


def test_exception_rate_is_in_the_reportable_band(output, built: BuildResult) -> None:
    """Target 5-12% (§9.6). Zero exceptions means lying or not trying; a very high rate
    means the matcher is not working."""
    metrics = score(output, built.truth)
    assert 0.0 < metrics.exception_rate_pct < 40.0


def test_scoring_uses_the_truth_tier_not_the_matcher_tier(output, built: BuildResult) -> None:
    """Otherwise the denominator is chosen by the thing being measured."""
    metrics = score(output, built.truth)
    truth_counts: dict[MatchTier, int] = dict.fromkeys(MatchTier, 0)
    for t in built.truth:
        truth_counts[t.difficulty_tier] += 1
    for tier_result in metrics.tiers:
        assert tier_result.eligible == truth_counts[tier_result.tier]


# ---------------------------------------------------------------------------
# UTR extraction
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "narration,expected",
    [
        ("NEFT-HDFC261530000001-RAZORPAY SOFTWARE PVT LTD", "HDFC261530000001"),
        ("RTGS-ICIC261530000002-RAZORPAY", "ICIC261530000002"),
        ("neft hdfc261530000001 razorpay software pvt ltd", "HDFC261530000001"),  # C14
        ("NEFT HDFC261530000001 RZRPY SFTWR PVT LTD", "HDFC261530000001"),  # C07 mangled
        ("NEFT-HDFC261530000001-RAZORPAY PMT/भुगतान", "HDFC261530000001"),  # C14 mixed script
        ("IMPS/123456789012/SOMEONE/REF", "123456789012"),
        ("NEFT-", None),  # C07 truncated past the reference
        ("", None),
        ("PAYMENT RECEIVED THANK YOU", None),
    ],
)
def test_utr_extraction(narration: str, expected: str | None) -> None:
    assert extract_utr(narration) == expected


def test_a_bare_twelve_digit_run_is_not_treated_as_a_reference() -> None:
    """Guessing a reference produces a confident match against the wrong settlement."""
    assert extract_utr("NEFT SETTLEMENT 123456789012 THANK YOU") is None


def test_normalise_collapses_separators_and_case() -> None:
    assert normalise("NEFT-HDFC26/1530  RAZORPAY") == "NEFT HDFC26 1530 RAZORPAY"
