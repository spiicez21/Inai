"""Gross→net tie-out, paise-exact. INAI_SPEC.md §6.1, §6.3.

Hand-built cases with hand-checked answers. These catch regressions the statistical tests
miss (DATA.md §8).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from inai.match.settlement_math import (
    DISPUTE_HOLD,
    FEE_TAX_VARIANCE,
    MISSING_REFUND_REVERSAL,
    SHORT_SETTLEMENT,
    UNSETTLED_CAPTURE,
    index_credits_by_utr,
    tie_out,
)
from inai.money import Paise
from inai.schema import BankCredit, LegType, Method, SettlementLeg

TS = datetime(2026, 6, 1, tzinfo=UTC)
VD = date(2026, 6, 2)
UTR = "HDFC261530000001"


def leg(
    entity_id: str,
    *,
    credit: int = 0,
    debit: int = 0,
    fee: int = 0,
    tax: int = 0,
    kind: LegType = LegType.PAYMENT,
    settled: bool = True,
) -> SettlementLeg:
    return SettlementLeg(
        entity_id=entity_id,
        type=kind,
        debit=Paise(debit),
        credit=Paise(credit),
        amount=Paise(credit or debit),
        fee=Paise(fee),
        tax=Paise(tax),
        settled=settled,
        created_at=TS,
        settled_at=TS if settled else None,
        settlement_id="setl_260602",
        settlement_utr=UTR,
        order_id="order_1",
        order_receipt="inv_0000001",
        method=Method.CARD,
    )


def credit(amount: int, *, line: str = "stmt_1", value_date: date = VD) -> BankCredit:
    return BankCredit(
        statement_line_id=line,
        value_date=value_date,
        amount_paise=Paise(amount),
        narration=f"NEFT-{UTR}-RAZORPAY SOFTWARE PVT LTD",
    )


def only(legs: list[SettlementLeg], credits: list[BankCredit], tol: int = 100):
    results = tie_out(legs, credits, tolerance_paise=tol)
    assert len(results) == 1
    return results[0]


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------
def test_clean_tie_out_is_paise_exact() -> None:
    """gross 1,00,000 − MDR 1,750 − GST 315 = 97,935 paise."""
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    result = only(legs, [credit(97_935)])
    assert int(result.expected_net_paise) == 97_935
    assert int(result.residual_paise) == 0
    assert result.clean
    assert result.attributed_to is None
    assert "ties out" in result.explanation


def test_a_single_paisa_out_is_not_clean_at_zero_tolerance() -> None:
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    result = only(legs, [credit(97_934)], tol=0)
    assert int(result.residual_paise) == -1
    assert not result.clean


def test_refunds_and_disputes_reduce_the_expected_net() -> None:
    legs = [
        leg("pay_1", credit=100_000, fee=1_750, tax=315),
        leg("rfnd_1", debit=20_000, kind=LegType.REFUND),
        leg("disp_1", debit=5_000, kind=LegType.DISPUTE, settled=False),
    ]
    result = only(legs, [credit(72_935)])
    assert int(result.expected_net_paise) == 100_000 - 1_750 - 315 - 20_000 - 5_000
    assert result.clean


def test_adjustments_increase_the_expected_net() -> None:
    legs = [
        leg("pay_1", credit=100_000, fee=1_750, tax=315),
        leg("adj_1", credit=500, kind=LegType.ADJUSTMENT),
    ]
    result = only(legs, [credit(98_435)])
    assert int(result.adjustment_paise) == 500
    assert result.clean


def test_upi_carries_no_mdr_so_net_equals_gross() -> None:
    legs = [leg("pay_1", credit=100_000, fee=0, tax=0)]
    result = only(legs, [credit(100_000)])
    assert int(result.fee_paise) == 0
    assert int(result.expected_net_paise) == 100_000


def test_lumped_settlement_of_many_orders() -> None:
    """The actual shape of the problem: one credit, many orders."""
    legs = [leg(f"pay_{i}", credit=10_000, fee=175, tax=32) for i in range(400)]
    expected = 400 * (10_000 - 175 - 32)
    result = only(legs, [credit(expected)])
    assert int(result.gross_paise) == 4_000_000
    assert result.clean


# ---------------------------------------------------------------------------
# Attribution — which component fails to reconcile
# ---------------------------------------------------------------------------
def test_missing_refund_reversal_is_named() -> None:
    """Refund debited from the merchant, never credited back. Rails leakage."""
    legs = [
        leg("pay_1", credit=100_000, fee=1_750, tax=315),
        leg("rfnd_1", debit=20_000, kind=LegType.REFUND),
    ]
    # The credit still carries the refund the merchant never got back.
    result = only(legs, [credit(97_935)])
    assert result.attributed_to == MISSING_REFUND_REVERSAL
    assert int(result.residual_paise) == 20_000


def test_dispute_hold_is_named() -> None:
    legs = [
        leg("pay_1", credit=100_000, fee=1_750, tax=315),
        leg("disp_1", debit=30_000, kind=LegType.DISPUTE, settled=False),
    ]
    result = only(legs, [credit(97_935)])
    assert result.attributed_to == DISPUTE_HOLD


def test_short_settlement_is_named() -> None:
    """Gateway paid materially less than computed."""
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    result = only(legs, [credit(50_000)])
    assert result.attributed_to == SHORT_SETTLEMENT
    assert int(result.residual_paise) < 0


def test_small_discrepancy_is_a_fee_variance_not_a_short_settlement() -> None:
    """Within the size of the deduction => the deduction is what moved."""
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    result = only(legs, [credit(97_935 - 500)])
    assert result.attributed_to == FEE_TAX_VARIANCE


def test_no_bank_credit_at_all_is_an_unsettled_capture() -> None:
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    result = only(legs, [])
    assert result.attributed_to == UNSETTLED_CAPTURE
    assert result.bank_ref is None
    assert "no bank credit" in result.explanation


def test_unsettled_leg_is_excluded_from_gross() -> None:
    """Captured but never settled: the gateway holds it, so it is not in this credit."""
    legs = [
        leg("pay_1", credit=100_000, fee=1_750, tax=315),
        leg("pay_2", credit=50_000, fee=875, tax=157, settled=False),
    ]
    result = only(legs, [credit(97_935)])
    assert int(result.gross_paise) == 100_000
    assert result.clean


# ---------------------------------------------------------------------------
# Duplicate credits — a finding, not an ambiguity to discard
# ---------------------------------------------------------------------------
def test_duplicate_credit_keeps_the_earliest_and_reports_the_rest() -> None:
    """Dropping both would make the ORIGINAL unfindable and hide the duplicate payment."""
    first = credit(97_935, line="stmt_1", value_date=date(2026, 6, 2))
    second = credit(97_935, line="stmt_1_dup", value_date=date(2026, 6, 3))
    primary, duplicates = index_credits_by_utr([second, first])  # deliberately out of order
    assert primary[UTR].statement_line_id == "stmt_1"
    assert [c.statement_line_id for c in duplicates[UTR]] == ["stmt_1_dup"]


def test_a_settlement_with_a_duplicate_credit_still_ties_out() -> None:
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    first = credit(97_935, line="stmt_1", value_date=date(2026, 6, 2))
    dup = credit(97_935, line="stmt_1_dup", value_date=date(2026, 6, 3))
    result = only(legs, [first, dup])
    assert result.clean, "the duplicate must not break the original settlement"
    assert result.bank_ref == "stmt_1"


def test_unresolvable_utr_leaves_no_credit_rather_than_a_wrong_one() -> None:
    legs = [leg("pay_1", credit=100_000, fee=1_750, tax=315)]
    mangled = BankCredit(
        statement_line_id="stmt_1",
        value_date=VD,
        amount_paise=Paise(97_935),
        narration="NEFT-",  # truncated past the UTR
    )
    result = only(legs, [mangled])
    assert result.bank_ref is None


@pytest.mark.parametrize("amount", [0, 1, 99, 100, 101, 10**12])
def test_no_float_creeps_into_the_arithmetic(amount: int) -> None:
    legs = [leg("pay_1", credit=amount)]
    result = only(legs, [credit(amount)])
    for component in result.components:
        assert isinstance(component.amount_paise, int)
    assert isinstance(result.residual_paise, int)
