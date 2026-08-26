"""The matcher's input and output contracts.

`match/**` may not import anything from `inai.sim` — not just `sim.truth`, the whole
package (see `tests/test_no_truth_leak.py`). So the matcher takes plain schema objects and
knows nothing about how they were produced. That is the point: it sees exactly what a real
merchant sees, three files with no answer key.

The orchestrator in `inai/pipeline.py` is what bridges the two, because it is allowed to
import both.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from inai.money import Paise
from inai.schema import BankCredit, Invoice, MatchResult, SettlementLeg


@dataclass(frozen=True, slots=True)
class ReconInput:
    """The three sides. Exactly what lands on a finance team's desk."""

    invoices: list[Invoice]
    legs: list[SettlementLeg]
    credits: list[BankCredit]

    def __post_init__(self) -> None:
        if not self.invoices:
            raise ValueError("recon input has no ledger side")


@dataclass(frozen=True, slots=True)
class Component:
    """One line of the gross→net bridge, in paise."""

    label: str
    amount_paise: Paise


@dataclass(frozen=True, slots=True)
class TieOut:
    """Gross→net for one settlement. INAI_SPEC.md §6.1.

    `residual` is the part of the bank credit no component explains.

    **The residual is the product.** Most recon tools stop at match/no-match; the number
    that matters to a finance team is the unexplained gap in rupees, and which component it
    is attributable to.
    """

    settlement_id: str
    utr: str
    bank_ref: str | None
    gross_paise: Paise
    fee_paise: Paise
    tax_paise: Paise
    refund_paise: Paise
    dispute_paise: Paise
    adjustment_paise: Paise
    tcs_paise: Paise
    expected_net_paise: Paise
    observed_net_paise: Paise
    residual_paise: Paise
    clean: bool
    #: Which component fails to reconcile, when one can be identified. Drives the
    #: SHORT_SETTLEMENT / FEE_TAX_VARIANCE / MISSING_REFUND_REVERSAL split in phase 3.
    attributed_to: str | None
    explanation: str

    @property
    def components(self) -> list[Component]:
        return [
            Component("gross", self.gross_paise),
            Component("mdr", self.fee_paise),
            Component("gst_on_mdr", self.tax_paise),
            Component("refunds", self.refund_paise),
            Component("disputes", self.dispute_paise),
            Component("adjustments", self.adjustment_paise),
            Component("tcs", self.tcs_paise),
        ]


@dataclass(slots=True)
class ReconOutput:
    matches: list[MatchResult] = field(default_factory=list)
    tie_outs: list[TieOut] = field(default_factory=list)

    @property
    def matched(self) -> list[MatchResult]:
        return [m for m in self.matches if m.matched]

    @property
    def unmatched(self) -> list[MatchResult]:
        return [m for m in self.matches if not m.matched]

    @property
    def total_residual_paise(self) -> Paise:
        return Paise(sum(abs(int(t.residual_paise)) for t in self.tie_outs))

    @property
    def attributed_residual_paise(self) -> Paise:
        return Paise(
            sum(abs(int(t.residual_paise)) for t in self.tie_outs if t.attributed_to is not None)
        )
