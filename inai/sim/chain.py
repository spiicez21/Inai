"""The generated chain: invoice → order → payment(s) → settlement leg(s) → bank credit.

Every link is known by construction (DATA.md §5 STEP 1), which is what makes ground truth
correct rather than hand-labelled. Corruption operators take a chain and return a chain, so
the truth recorded at generation time always refers to the *uncorrupted* answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from inai.money import Paise
from inai.schema import BankCredit, Invoice, MatchTier, SettlementLeg
from inai.sim.truth import LatentState


@dataclass(slots=True)
class Settlement:
    """One settlement cycle: many legs, one UTR, one lumped bank credit.

    `expected_net` is the arithmetic the matcher must later rediscover from the outside
    (INAI_SPEC.md §6.1):

        Σ payment.credit − Σ fee − Σ tax − Σ refund.debit − Σ dispute.debit
        − TCS + Σ adjustment.credit
    """

    settlement_id: str
    utr: str
    value_date: date
    legs: list[SettlementLeg] = field(default_factory=list)
    tcs_paise: Paise = field(default=Paise(0))

    def expected_net(self) -> Paise:
        total = 0
        for leg in self.legs:
            total += int(leg.credit) - int(leg.debit) - int(leg.fee) - int(leg.tax)
        return Paise(total - int(self.tcs_paise))


@dataclass(slots=True)
class LedgerChain:
    """One invoice and everything downstream of it."""

    invoice: Invoice
    legs: list[SettlementLeg]
    settlement_id: str | None
    #: Populated after settlements are assembled — a chain's credit is shared with every
    #: other chain in the same settlement, which is the whole point.
    bank_ref: str | None = None

    # --- ground truth, recorded before any corruption ---------------------
    latent_state: LatentState = LatentState.SELF_CURING
    operators_fired: tuple[str, ...] = ()
    #: Tier is the HARDEST tier among the operators that fired. Recomputed by `with_operator`.
    difficulty_tier: MatchTier = MatchTier.T0_EXACT

    def with_operator(self, op_id: str, tier: MatchTier) -> None:
        """Record that an operator fired, and escalate the difficulty tier if needed."""
        if op_id not in self.operators_fired:
            self.operators_fired = (*self.operators_fired, op_id)
        order = list(MatchTier)
        if order.index(tier) > order.index(self.difficulty_tier):
            self.difficulty_tier = tier

    @property
    def gross_paise(self) -> Paise:
        return Paise(sum(int(leg.credit) for leg in self.legs))


@dataclass(slots=True)
class Batch:
    """Everything one run generates."""

    chains: list[LedgerChain]
    settlements: dict[str, Settlement]
    credits: list[BankCredit]

    def credit_by_id(self, statement_line_id: str) -> BankCredit | None:
        return next((c for c in self.credits if c.statement_line_id == statement_line_id), None)

    def replace_credit(self, statement_line_id: str, **changes: object) -> None:
        """Swap one credit for a modified copy.

        `BankCredit` is a frozen Pydantic model, so this is `model_copy`, not
        `dataclasses.replace` — corruption operators must not mutate a validated record in
        place or the schema guarantees stop meaning anything.
        """
        for i, c in enumerate(self.credits):
            if c.statement_line_id == statement_line_id:
                self.credits[i] = c.model_copy(update=changes)
                return
