"""Corruption operators. DATA.md §5.1.

Fourteen documented real-world failure modes, applied *after* truth is recorded. This is
what removes the "your data is fake" objection: we never hand-label anything, because the
answer existed before the damage did.

Each operator records that it fired on a chain, and a chain's difficulty tier is the
**hardest** tier among the operators that fired on it (DATA.md §5.2). That is what lets the
scorecard report match rate per tier instead of one blended number dominated by matches
that were never hard.

Two operator kinds, because the spec's per-record Protocol cannot express all fourteen:

  * `RecordOperator` — acts on one chain. Twelve of them.
  * `BatchOperator`  — needs several chains at once. C02 (bundle N invoices into one
    credit) and C09 (duplicate a credit) genuinely cannot be expressed per-record.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

import numpy as np

from inai.money import Paise
from inai.schema import InvoiceStatus, LegType, MatchTier, SettlementLeg
from inai.sim.chain import Batch, LedgerChain

# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


class RecordOperator(Protocol):
    id: str
    tier_contribution: MatchTier
    #: True for operators that REWRITE the shared bank credit's narration.
    #:
    #: A settlement's credit is shared by every order in that cycle — about 57 of them at
    #: demo scale. An operator applied per-chain therefore fires ~57 times on the same
    #: string, so a nominal 12% rate becomes an effective ~100%, and repeated truncation
    #: and case-scrambling shredded 56% of UTRs beyond recovery.
    #:
    #: Amount-shifting operators are deliberately NOT flagged: several orders in one
    #: settlement each having a fee variance or a dropped refund is real, and their effects
    #: genuinely accumulate on the credit. Rewriting one string 57 times is not real.
    once_per_credit: bool

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool: ...
    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None: ...


class BatchOperator(Protocol):
    id: str
    tier_contribution: MatchTier

    def apply_batch(self, batch: Batch, rate: float, rng: np.random.Generator) -> None: ...


def _leg_index(chain: LedgerChain, leg: SettlementLeg) -> int:
    return next(i for i, x in enumerate(chain.legs) if x.entity_id == leg.entity_id)


def _swap_leg(chain: LedgerChain, batch: Batch, old: SettlementLeg, new: SettlementLeg) -> None:
    """Replace a leg in both the chain and its settlement, keeping them consistent."""
    chain.legs[_leg_index(chain, old)] = new
    s = batch.settlements.get(chain.settlement_id or "")
    if s is not None:
        for i, x in enumerate(s.legs):
            if x.entity_id == old.entity_id:
                s.legs[i] = new
                break


def _shift_credit(batch: Batch, chain: LedgerChain, delta_paise: int) -> None:
    """Move the settlement's bank credit by `delta`, leaving an unexplained residual."""
    if chain.bank_ref is None:
        return
    credit = batch.credit_by_id(chain.bank_ref)
    if credit is None:
        return
    batch.replace_credit(chain.bank_ref, amount_paise=Paise(int(credit.amount_paise) + delta_paise))


# ---------------------------------------------------------------------------
# C01 · Strip remittance reference                                        → T2
# ---------------------------------------------------------------------------
class C01_StripReference:
    """Payment message arrives with no invoice reference at all.

    The single most common cause of unapplied cash: money is in the bank, and nothing on
    the credit says which invoice it settles.
    """

    id = "C01"
    once_per_credit = False
    tier_contribution = MatchTier.T2_FUZZY

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return any(leg.order_receipt is not None for leg in chain.legs)

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        # BOTH references, not just the receipt. `order_receipt` is the merchant's own
        # number and `order_id` is the gateway's; a payment message that arrives with no
        # invoice reference has neither. Clearing only one leaves a perfect join key in
        # place, so the operator claims to make matching hard while changing nothing —
        # which showed up as T4 scoring 95% against a "<50% expected" target.
        for leg in list(chain.legs):
            _swap_leg(chain, batch, leg, dc_replace_leg(leg, order_receipt=None, order_id=None))


# ---------------------------------------------------------------------------
# C03 · Split one invoice across payments                                 → T3
# ---------------------------------------------------------------------------
class C03_SplitPayment:
    """Olist `payment_sequential` — real behaviour, made harder.

    The invoice is only partly covered, so the ledger and the settlement disagree by a
    genuine shortfall rather than by a bookkeeping artefact.
    """

    id = "C03"
    once_per_credit = False
    tier_contribution = MatchTier.T3_STRUCTURAL

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return len(chain.legs) == 1 and int(chain.legs[0].credit) > 20_000

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        leg = chain.legs[0]
        share = float(rng.uniform(0.35, 0.7))
        part = Paise(int(int(leg.credit) * share))
        shortfall = int(leg.credit) - int(part)
        new = dc_replace_leg(leg, credit=part, amount=part)
        _swap_leg(chain, batch, leg, new)
        _shift_credit(batch, chain, -shortfall)
        chain.invoice = chain.invoice.model_copy(update={"status": InvoiceStatus.PARTIAL})


# ---------------------------------------------------------------------------
# C04 · Shift settlement T+1…T+7                                          → T1
# ---------------------------------------------------------------------------
class C04_TimingShift:
    """Variable settlement cycle by gateway and merchant tier.

    Produces `TIMING_DIFFERENCE`: the money will arrive, just not in the window the ledger
    expected. Chasing these is false dunning.
    """

    id = "C04"
    once_per_credit = False
    tier_contribution = MatchTier.T1_DETERMINISTIC

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return bool(chain.legs)

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        shift = timedelta(days=int(rng.integers(1, 8)))
        for leg in list(chain.legs):
            if leg.settled_at is None:
                continue
            _swap_leg(chain, batch, leg, dc_replace_leg(leg, settled_at=leg.settled_at + shift))


# ---------------------------------------------------------------------------
# C05 · Perturb fee ±δ                                                    → T1
# ---------------------------------------------------------------------------
class C05_FeeVariance:
    """MDR rounding, tier changes, method mix drift.

    Small, but it is the class that makes a tie-out fail by a few paise and sends a human
    hunting for an hour. Attributing it in rupees is the product.
    """

    id = "C05"
    once_per_credit = False
    tier_contribution = MatchTier.T1_DETERMINISTIC

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return any(int(leg.fee) > 0 for leg in chain.legs)

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        delta_total = 0
        for leg in list(chain.legs):
            if int(leg.fee) <= 0:
                continue
            delta = int(int(leg.fee) * float(rng.uniform(-0.25, 0.35)))
            if delta == 0:
                continue
            _swap_leg(chain, batch, leg, dc_replace_leg(leg, fee=Paise(int(leg.fee) + delta)))
            delta_total += delta
        # The bank credit keeps the OLD net: the deduction changed, the money did not.
        _shift_credit(batch, chain, delta_total)


# ---------------------------------------------------------------------------
# C06 · Drop a refund reversal                                            → T1
# ---------------------------------------------------------------------------
class C06_MissingRefundReversal:
    """Refund debited from the merchant, never credited back by the gateway.

    Rails leakage: real money, owed to the merchant, invisible without reconciliation.
    """

    id = "C06"
    once_per_credit = False
    tier_contribution = MatchTier.T1_DETERMINISTIC

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return bool(chain.legs) and int(chain.legs[0].credit) > 5_000

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        src = chain.legs[0]
        amount = Paise(int(int(src.credit) * float(rng.uniform(0.2, 0.6))))
        refund = SettlementLeg(
            entity_id=f"rfnd_{src.entity_id[4:]}",
            type=LegType.REFUND,
            debit=amount,
            credit=Paise(0),
            amount=amount,
            fee=Paise(0),
            tax=Paise(0),
            settled=True,
            created_at=src.created_at,
            settled_at=src.settled_at,
            settlement_id=src.settlement_id,
            settlement_utr=src.settlement_utr,
            order_id=src.order_id,
            order_receipt=src.order_receipt,
            method=src.method,
        )
        chain.legs.append(refund)
        s = batch.settlements.get(chain.settlement_id or "")
        if s is not None:
            s.legs.append(refund)
        # The debit is recorded but never reaches the bank credit — that IS the leak.
        _shift_credit(batch, chain, int(amount))


# ---------------------------------------------------------------------------
# C07 · Mangle / truncate narration                                       → T2
# ---------------------------------------------------------------------------
class C07_MangleNarration:
    """Bank field limits, OCR, abbreviation. DATA.md §4.1 names this the weakest link."""

    id = "C07"
    once_per_credit = True
    tier_contribution = MatchTier.T2_FUZZY

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return chain.bank_ref is not None

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        credit = batch.credit_by_id(chain.bank_ref or "")
        if credit is None:
            return
        text = credit.narration
        mode = int(rng.integers(0, 3))
        if mode == 0:  # hard truncation at a bank field limit
            text = text[: int(rng.integers(18, 30))]
        elif mode == 1:  # separators collapse
            text = text.replace("-", " ").replace("/", " ")
            text = " ".join(text.split())
        else:  # vowels dropped from the remitter, as abbreviation does
            head, _, tail = text.partition("RAZORPAY")
            text = head + "RZRPY" + tail.replace("SOFTWARE", "SFTWR")
        batch.replace_credit(chain.bank_ref or "", narration=text)


# ---------------------------------------------------------------------------
# C08 · Pay from a parent-company account                                 → T4
# ---------------------------------------------------------------------------
class C08_ParentCompanyPayer:
    """Customers pay with their parent company's bank account.

    Wrong-payer identity. Expect to lose most of these, and report the loss.
    """

    id = "C08"
    once_per_credit = True
    tier_contribution = MatchTier.T4_ADVERSARIAL

    _PARENTS = (
        "ADITYA BIRLA MGMT CORP",
        "TATA SONS PVT LTD",
        "RELIANCE CORP IT PARK",
        "MAHINDRA HOLDINGS LTD",
        "GODREJ INDUSTRIES LTD",
    )

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return chain.bank_ref is not None

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        credit = batch.credit_by_id(chain.bank_ref or "")
        if credit is None:
            return
        parent = self._PARENTS[int(rng.integers(0, len(self._PARENTS)))]
        batch.replace_credit(
            chain.bank_ref or "",
            narration=credit.narration.replace("RAZORPAY SOFTWARE PVT LTD", parent),
            counterparty_guess=parent,
        )


# ---------------------------------------------------------------------------
# C10 · Unexplained deduction                                             → T4
# ---------------------------------------------------------------------------
class C10_UnexplainedDeduction:
    """Customers deduct amounts you have never heard of.

    No leg explains it, so the residual is genuinely unattributable — which is exactly the
    case where an honest exception beats a confident guess.
    """

    id = "C10"
    once_per_credit = False
    tier_contribution = MatchTier.T4_ADVERSARIAL

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return chain.bank_ref is not None and int(chain.gross_paise) > 10_000

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        cut = int(int(chain.gross_paise) * float(rng.uniform(0.01, 0.08)))
        _shift_credit(batch, chain, -cut)


# ---------------------------------------------------------------------------
# C11 · Capture without settlement                                        → T1
# ---------------------------------------------------------------------------
class C11_UnsettledCapture:
    """Payment captured, settlement never formed. Money owed, sitting at the gateway."""

    id = "C11"
    once_per_credit = False
    tier_contribution = MatchTier.T1_DETERMINISTIC

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return bool(chain.legs)

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        leg = chain.legs[0]
        _swap_leg(chain, batch, leg, dc_replace_leg(leg, settled=False, settled_at=None))
        _shift_credit(batch, chain, -(int(leg.credit) - int(leg.fee) - int(leg.tax)))


# ---------------------------------------------------------------------------
# C12 · Chargeback mid-flight                                             → T1
# ---------------------------------------------------------------------------
class C12_DisputeHold:
    """Dispute raised, funds withheld. Chasing this payer would be illegal, not merely rude."""

    id = "C12"
    once_per_credit = False
    tier_contribution = MatchTier.T1_DETERMINISTIC

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return bool(chain.legs)

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        src = chain.legs[0]
        dispute_id = f"disp_{src.entity_id[4:]}"
        dispute = SettlementLeg(
            entity_id=dispute_id,
            type=LegType.DISPUTE,
            debit=src.credit,
            credit=Paise(0),
            amount=src.credit,
            fee=Paise(0),
            tax=Paise(0),
            on_hold=True,
            settled=False,
            created_at=src.created_at,
            settled_at=None,
            settlement_id=src.settlement_id,
            settlement_utr=src.settlement_utr,
            order_id=src.order_id,
            order_receipt=src.order_receipt,
            method=src.method,
            dispute_id=dispute_id,
        )
        chain.legs.append(dispute)
        s = batch.settlements.get(chain.settlement_id or "")
        if s is not None:
            s.legs.append(dispute)
        chain.invoice = chain.invoice.model_copy(update={"status": InvoiceStatus.DISPUTED})
        _shift_credit(batch, chain, int(src.credit))


# ---------------------------------------------------------------------------
# C13 · Cancel invoice post-capture                                       → T3
# ---------------------------------------------------------------------------
class C13_CancelPostCapture:
    """Online Retail II `C`-prefixed cancellations: invoice cancelled after capture.

    Negative reconciliation — the ledger says nothing is owed, the money arrived anyway.
    """

    id = "C13"
    once_per_credit = False
    tier_contribution = MatchTier.T3_STRUCTURAL

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return chain.invoice.status is not InvoiceStatus.DISPUTED

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        chain.invoice = chain.invoice.model_copy(update={"status": InvoiceStatus.WRITTEN_OFF})


# ---------------------------------------------------------------------------
# C14 · Mixed-language / casing narration                                 → T2
# ---------------------------------------------------------------------------
class C14_MixedCasing:
    """Real Indian bank statements, in the wild."""

    id = "C14"
    once_per_credit = True
    tier_contribution = MatchTier.T2_FUZZY

    def applies_to(self, chain: LedgerChain, rng: np.random.Generator) -> bool:
        return chain.bank_ref is not None

    def apply(self, chain: LedgerChain, batch: Batch, rng: np.random.Generator) -> None:
        credit = batch.credit_by_id(chain.bank_ref or "")
        if credit is None:
            return
        text = credit.narration
        mode = int(rng.integers(0, 3))
        if mode == 0:
            text = text.lower()
        elif mode == 1:
            text = "".join(c.upper() if rng.random() < 0.5 else c.lower() for c in text)
        else:
            text = f"{text} PMT/भुगतान"
        batch.replace_credit(chain.bank_ref or "", narration=text)


# ---------------------------------------------------------------------------
# Batch-level operators
# ---------------------------------------------------------------------------
class C02_BundleInvoices:
    """Bundle N invoices into one credit.                                    → T3

    A customer with several open invoices pays one lump covering all of them. This is the
    subset-sum case, and it cannot be expressed per-record: it needs several chains at once.
    """

    id = "C02"
    once_per_credit = False
    tier_contribution = MatchTier.T3_STRUCTURAL

    def apply_batch(self, batch: Batch, rate: float, rng: np.random.Generator) -> None:
        by_customer: dict[str, list[LedgerChain]] = {}
        for c in batch.chains:
            by_customer.setdefault(c.invoice.customer_id, []).append(c)

        for chains in by_customer.values():
            if len(chains) < 2 or rng.random() >= rate:
                continue
            group = chains[: min(len(chains), int(rng.integers(2, 5)))]
            # They all now point at the FIRST chain's credit: one lump, several invoices.
            target = group[0].bank_ref
            if target is None:
                continue
            moved = 0
            for other in group[1:]:
                if other.bank_ref is None or other.bank_ref == target:
                    continue
                src = batch.credit_by_id(other.bank_ref)
                if src is None:
                    continue
                moved += int(src.amount_paise)
                batch.replace_credit(other.bank_ref, amount_paise=Paise(0))
                other.bank_ref = target
                other.with_operator(self.id, self.tier_contribution)
            if moved:
                dst = batch.credit_by_id(target)
                if dst is not None:
                    batch.replace_credit(target, amount_paise=Paise(int(dst.amount_paise) + moved))
                group[0].with_operator(self.id, self.tier_contribution)


class C09_DuplicateCredit:
    """Duplicate a credit.                                                   → T4

    Double submission. The merchant has been paid twice; the correct action is a credit
    note, and chasing the customer would be actively wrong.
    """

    id = "C09"
    once_per_credit = False
    tier_contribution = MatchTier.T4_ADVERSARIAL

    def apply_batch(self, batch: Batch, rate: float, rng: np.random.Generator) -> None:
        # One credit can only be double-submitted ONCE. Chains sharing a settlement share a
        # credit, so without this guard several chains each emit `<id>_dup` and collide on
        # the store's primary key — and "the same lump paid three extra times" is not a
        # failure mode anyone has ever seen.
        already: set[str] = set()
        for chain in list(batch.chains):
            if chain.bank_ref is None or chain.bank_ref in already or rng.random() >= rate:
                continue
            src = batch.credit_by_id(chain.bank_ref)
            if src is None:
                continue
            already.add(chain.bank_ref)
            batch.credits.append(
                src.model_copy(
                    update={
                        "statement_line_id": f"{src.statement_line_id}_dup",
                        "value_date": src.value_date + timedelta(days=1),
                    }
                )
            )
            chain.with_operator(self.id, self.tier_contribution)


# ---------------------------------------------------------------------------
# Registry and driver
# ---------------------------------------------------------------------------
RECORD_OPERATORS: tuple[RecordOperator, ...] = (
    C01_StripReference(),
    C03_SplitPayment(),
    C04_TimingShift(),
    C05_FeeVariance(),
    C06_MissingRefundReversal(),
    C07_MangleNarration(),
    C08_ParentCompanyPayer(),
    C10_UnexplainedDeduction(),
    C11_UnsettledCapture(),
    C12_DisputeHold(),
    C13_CancelPostCapture(),
    C14_MixedCasing(),
)

BATCH_OPERATORS: tuple[BatchOperator, ...] = (C02_BundleInvoices(), C09_DuplicateCredit())

ALL_OPERATOR_IDS: tuple[str, ...] = tuple(
    sorted([op.id for op in RECORD_OPERATORS] + [op.id for op in BATCH_OPERATORS])
)


def corrupt(batch: Batch, rates: dict[str, float], rng: np.random.Generator) -> Batch:
    """Apply every configured operator. DATA.md §5 STEP 3.

    Each operator gets its own RNG stream (`rng.spawn`), keyed by position in a *sorted*
    list of ids. Sharing one generator would make the output depend on operator order, so
    reordering the registry would silently change every generated record and quietly break
    the reproducibility claim on the closing slide.
    """
    streams = dict(zip(ALL_OPERATOR_IDS, rng.spawn(len(ALL_OPERATOR_IDS)), strict=True))

    for op in RECORD_OPERATORS:
        rate = float(rates.get(op.id, 0.0))
        if rate <= 0:
            continue
        op_rng = streams[op.id]
        touched_credits: set[str] = set()
        for chain in batch.chains:
            if op.once_per_credit and chain.bank_ref in touched_credits:
                continue
            if op_rng.random() < rate and op.applies_to(chain, op_rng):
                op.apply(chain, batch, op_rng)
                chain.with_operator(op.id, op.tier_contribution)
                if op.once_per_credit and chain.bank_ref is not None:
                    touched_credits.add(chain.bank_ref)

    for bop in BATCH_OPERATORS:
        rate = float(rates.get(bop.id, 0.0))
        if rate > 0:
            bop.apply_batch(batch, rate, streams[bop.id])

    return batch


def dc_replace_leg(leg: SettlementLeg, **changes: object) -> SettlementLeg:
    """`SettlementLeg` is a frozen Pydantic model, so this is `model_copy`."""
    return leg.model_copy(update=changes)
