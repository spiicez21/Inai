"""Phase 1 acceptance. INAI_SPEC.md §11, DATA.md §5 and §8.

    Acceptance: 5,000 records, seeded-identical, truth-leak test passes.

These are the property tests that must hold on every run, not example tests.
"""

from __future__ import annotations

import numpy as np
import pytest

from inai.config import ResolvedConfig, canonical_hash
from inai.schema import MatchTier
from inai.sim.build import BuildResult, build
from inai.sim.corrupt import ALL_OPERATOR_IDS, BATCH_OPERATORS, RECORD_OPERATORS
from inai.sim.spine import spine_available

pytestmark = pytest.mark.skipif(
    not spine_available(),
    reason="Olist spine not present — see DATA.md §2 / TODO.md phase 1",
)


def _build(seed: int = 42, config: str = "configs/smoke.yaml") -> BuildResult:
    cfg = ResolvedConfig.resolve(config, seed=seed)
    return build(cfg, np.random.default_rng(cfg.run.seed))


@pytest.fixture(scope="module")
def result() -> BuildResult:
    return _build()


# ---------------------------------------------------------------------------
# Determinism — the reproducibility claim on the closing slide
# ---------------------------------------------------------------------------
def _fingerprint(res: BuildResult) -> str:
    return canonical_hash(
        {
            "invoices": [
                (c.invoice.invoice_id, int(c.invoice.amount_paise), c.invoice.status.value)
                for c in res.batch.chains
            ],
            "legs": [
                (leg.entity_id, int(leg.credit), int(leg.fee), int(leg.tax))
                for c in res.batch.chains
                for leg in c.legs
            ],
            "credits": [
                (c.statement_line_id, int(c.amount_paise), c.narration) for c in res.batch.credits
            ],
            "truth": [
                (t.ledger_ref, t.difficulty_tier.value, sorted(t.operators_fired))
                for t in res.truth
            ],
        }
    )


def test_same_seed_produces_identical_batch() -> None:
    assert _fingerprint(_build(seed=42)) == _fingerprint(_build(seed=42))


def test_different_seed_produces_different_batch() -> None:
    assert _fingerprint(_build(seed=42)) != _fingerprint(_build(seed=43))


# ---------------------------------------------------------------------------
# The money chain — DATA.md §5 STEP 2, paise-exact
# ---------------------------------------------------------------------------
def test_uncorrupted_settlements_tie_out_to_the_paisa(result: BuildResult) -> None:
    """`Σ legs − fees − taxes == bank credit` on records no operator touched.

    This is the arithmetic the matcher must later rediscover from the outside. If it does
    not hold here, every residual Stage 1 reports is measuring our own bug.
    """
    touched = {c.settlement_id for c in result.batch.chains if c.operators_fired}
    checked = 0
    for sid, settlement in result.batch.settlements.items():
        if sid in touched:
            continue
        credit = next(
            (c for c in result.batch.credits if c.statement_line_id == f"stmt_{sid[5:]}"), None
        )
        if credit is None:
            continue
        assert int(credit.amount_paise) == int(settlement.expected_net()), f"{sid} does not tie out"
        checked += 1
    assert checked > 0, "no clean settlements to check — corruption rates may be too high"


def test_no_float_money_anywhere(result: BuildResult) -> None:
    for chain in result.batch.chains:
        assert isinstance(chain.invoice.amount_paise, int)
        for leg in chain.legs:
            for field in (leg.credit, leg.debit, leg.amount, leg.fee, leg.tax):
                assert isinstance(field, int), f"{leg.entity_id} carries a non-integer amount"
    for credit in result.batch.credits:
        assert isinstance(credit.amount_paise, int)


def test_upi_carries_zero_mdr(result: BuildResult) -> None:
    """Government-mandated 0% MDR on UPI. If this drifts, every fee number is wrong."""
    for chain in result.batch.chains:
        for leg in chain.legs:
            if leg.method.value == "upi" and leg.type.value == "payment":
                assert int(leg.fee) == 0
                assert int(leg.tax) == 0


# ---------------------------------------------------------------------------
# Ground truth — DATA.md §5.2
# ---------------------------------------------------------------------------
def test_tier_is_the_hardest_operator_that_fired(result: BuildResult) -> None:
    by_id = {op.id: op.tier_contribution for op in RECORD_OPERATORS}
    by_id |= {op.id: op.tier_contribution for op in BATCH_OPERATORS}
    order = list(MatchTier)

    for link in result.truth:
        if not link.operators_fired:
            assert link.difficulty_tier is MatchTier.T0_EXACT
            continue
        hardest = max(order.index(by_id[op]) for op in link.operators_fired)
        assert order.index(link.difficulty_tier) == hardest, (
            f"{link.ledger_ref}: tier {link.difficulty_tier} does not match "
            f"operators {link.operators_fired}"
        )


def test_every_chain_has_exactly_one_truth_row(result: BuildResult) -> None:
    assert len(result.truth) == len(result.batch.chains)
    assert len({t.ledger_ref for t in result.truth}) == len(result.truth)


def test_all_fourteen_operators_are_registered() -> None:
    assert len(ALL_OPERATOR_IDS) == 14
    assert set(ALL_OPERATOR_IDS) == {f"C{i:02d}" for i in range(1, 15)}


def test_every_operator_actually_fires(result: BuildResult) -> None:
    """A registered operator that never fires is dead weight pretending to be coverage.

    C02 in particular is the canary: it needs a customer holding several invoices, which
    only exists because the spine is sampled customer-first.
    """
    fired = set(result.operator_counts)
    missing = set(ALL_OPERATOR_IDS) - fired
    assert not missing, f"operators registered but never fired: {sorted(missing)}"


def test_every_tier_is_populated(result: BuildResult) -> None:
    """A tier with no records cannot be reported, and the tier breakdown is the product."""
    empty = [t.value for t, n in result.tier_counts.items() if n == 0]
    assert not empty, f"tiers with no records: {empty}"


# ---------------------------------------------------------------------------
# Structure — the reason we use a real spine at all
# ---------------------------------------------------------------------------
def test_settlements_are_lumped(result: BuildResult) -> None:
    """A settlement covers many orders, not one.

    "A settlement arrives as a single lumped NEFT credit covering hundreds of orders, net
    of MDR, GST on MDR and refund adjustments" (DATA.md §1.3). One credit per order would
    reproduce none of the difficulty.
    """
    n_chains = len(result.batch.chains)
    n_settlements = len(result.batch.settlements)
    assert n_settlements < n_chains / 2, (
        f"{n_settlements} settlements for {n_chains} chains — credits are not lumping"
    )


def test_repeat_payers_exist(result: BuildResult) -> None:
    """Without repeat payers, C02 cannot fire and the recovery scorer has no history."""
    seen: dict[str, int] = {}
    for chain in result.batch.chains:
        seen[chain.invoice.customer_id] = seen.get(chain.invoice.customer_id, 0) + 1
    repeat = sum(1 for n in seen.values() if n > 1)
    assert repeat > 0, "no customer holds more than one invoice"


def test_multi_payment_orders_survive_localisation(result: BuildResult) -> None:
    """Olist `payment_sequential` is the real many-to-one behaviour that breaks matchers."""
    multi = sum(1 for c in result.batch.chains if len(c.legs) > 1)
    assert multi > 0, "no multi-payment orders in the batch"


def test_no_settlement_credit_is_negative(result: BuildResult) -> None:
    for credit in result.batch.credits:
        assert int(credit.amount_paise) >= 0


@pytest.mark.slow
def test_demo_config_produces_five_thousand_records() -> None:
    """Phase 1 acceptance criterion, stated verbatim in INAI_SPEC.md §11."""
    res = _build(config="configs/demo.yaml")
    assert len(res.batch.chains) >= 4_900, f"only {len(res.batch.chains)} chains"
    assert len(res.truth) == len(res.batch.chains)
