"""Money invariants. A rupee-conversion bug in a reconciler is fatal and embarrassing."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from inai.money import Paise, format_inr, parse_rupees, to_rupees


def test_float_trap() -> None:
    """The exact bug this module exists to prevent.

    ₹0.29 is not representable in binary floating point: 0.29 * 100 == 28.999999999999996,
    so the naive conversion silently loses a paisa. Across a 5,000-record settlement this is
    not a rounding nit — it is a tie-out that never closes and a residual you cannot explain.
    """
    for rupees, naive_wrong, correct in [(0.29, 28, 29), (0.57, 56, 57), (1.13, 112, 113)]:
        assert int(rupees * 100) == naive_wrong  # what naive code does
        assert parse_rupees(str(rupees)) == correct  # what we do


def test_indian_digit_grouping() -> None:
    # Lakh grouping, not thousands. Get this wrong in front of Razorpay judges and it shows.
    assert format_inr(Paise(123456789)) == "₹12,34,567.89"
    assert format_inr(Paise(100000)) == "₹1,000.00"
    assert format_inr(Paise(10000000)) == "₹1,00,000.00"
    assert format_inr(Paise(-123456789)) == "-₹12,34,567.89"
    assert format_inr(Paise(0)) == "₹0.00"
    assert format_inr(Paise(7)) == "₹0.07"


@given(st.integers(min_value=-(10**14), max_value=10**14))
def test_paise_rupee_roundtrip(paise: int) -> None:
    assert parse_rupees(to_rupees(Paise(paise))) == paise


@given(st.decimals(min_value=Decimal("-1e9"), max_value=Decimal("1e9"), places=2))
def test_rupee_parse_is_exact(rupees: Decimal) -> None:
    assert to_rupees(parse_rupees(rupees)) == rupees.quantize(Decimal("0.01"))


def test_half_up_rounding() -> None:
    assert parse_rupees("0.005") == 1  # not banker's rounding — money rounds half up
    assert parse_rupees("0.015") == 2
