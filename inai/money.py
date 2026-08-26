"""Money is an integer number of paise. Always. Everywhere. Internally.

INAI_SPEC.md §5.2: "Amounts in paise, integer, exactly as Razorpay returns them. Never float.
Never rupees internally. A rupee-conversion bug in a reconciler is fatal and embarrassing."

The only two places rupees are allowed to exist:
  * `parse_rupees` — at the CSV/JSON boundary, on the way in.
  * `format_inr`   — at the render boundary, on the way out.

Nothing between those two functions may hold a float or a Decimal.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import NewType

Paise = NewType("Paise", int)
"""An integer count of paise. 100 paise = ₹1."""

ZERO = Paise(0)


def parse_rupees(value: str | int | float | Decimal) -> Paise:
    """Boundary conversion: a rupee figure from a source file -> exact paise.

    Uses Decimal, not float. ``float("1234.55") * 100`` is 123454.99999999999.
    """
    d = Decimal(str(value)) * 100
    return Paise(int(d.to_integral_value(rounding=ROUND_HALF_UP)))


def to_rupees(paise: Paise) -> Decimal:
    """Boundary conversion for display/export only. Never feed this back into arithmetic."""
    return (Decimal(int(paise)) / 100).quantize(Decimal("0.01"))


def format_inr(paise: Paise) -> str:
    """Indian digit grouping: ₹12,34,567.89 — not ₹1,234,567.89.

    The frontend does this with Intl.NumberFormat("en-IN"); this is the Python twin,
    for CLI output and the audit export.
    """
    sign = "-" if paise < 0 else ""
    whole, frac = divmod(abs(int(paise)), 100)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join([*groups, tail])
    return f"{sign}₹{s}.{frac:02d}"


def pct(numerator: int, denominator: int) -> float:
    """Percentage that returns 0.0 rather than exploding on an empty tier."""
    return 0.0 if denominator == 0 else (numerator / denominator) * 100.0
