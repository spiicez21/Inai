"""The tiered matching cascade. INAI_SPEC.md §6.2.

    T0  extracted_utr ↔ settlement_utr, or order_id ↔ order_receipt, unique both ways.
        Should be near 100%. SAY OUT LOUD THAT IT PROVES NOTHING.
    T1  amount within ±₹1, value_date within the settlement window, payer consistent.
    T2  fuzzy narration                                            → phase 3
    T3  bundled / split / partial                                  → phase 3
    T4  parent-co payer, unexplained deduction, duplicate          → phase 3

Each tier runs only on what the previous tier left unmatched, and the tier is recorded on
every match — because a blended match rate is dominated by exact-reference matches that
were never hard, and reporting one number is what every vendor does.

Deterministic. No LLM in the match decision (§8.7).

**Ambiguity rule (§6.2):** if two allocations are equally plausible, do NOT pick one. A
confident wrong allocation silently closes an invoice that was never paid, which is worse
than an honest exception.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from inai.match.settlement_math import index_credits_by_utr, tie_out
from inai.match.types import ReconInput, ReconOutput, TieOut
from inai.money import Paise, format_inr
from inai.schema import BankCredit, Invoice, LegType, MatchResult, MatchTier, SettlementLeg

#: T1 date window. A settlement forms T+1…T+7 (INAI_SPEC.md §3.1), and C04 shifts it by up
#: to another 7 days, so the window a *matcher* must tolerate is wider than the nominal one.
T1_WINDOW_DAYS = 15


@dataclass(slots=True)
class _Index:
    """Everything the cascade needs, built once."""

    legs_by_receipt: dict[str, list[SettlementLeg]]
    legs_by_order: dict[str, list[SettlementLeg]]
    legs_by_settlement: dict[str, list[SettlementLeg]]
    credit_by_utr: dict[str, BankCredit]
    utr_by_settlement: dict[str, str]
    #: Settlement legs that no reference points at — the pool T1 searches by amount.
    unclaimed: list[SettlementLeg]
    #: UTR → credits that arrived after the settlement's own. Feeds DUPLICATE_PAYMENT.
    duplicate_credits: dict[str, list[BankCredit]]


def match(
    data: ReconInput,
    tolerance_paise: int = 100,
    settle_tolerance_paise: int = 100,
) -> ReconOutput:
    """Run the cascade over one batch.

    Conservation is structural, not checked afterwards: every invoice produces exactly one
    `MatchResult`, matched or not. `Σ matched + Σ exceptions == Σ input` therefore cannot
    fail silently — it is the shape of the loop.
    """
    tie_outs = tie_out(data.legs, data.credits, tolerance_paise=settle_tolerance_paise)
    index = _build_index(data)
    tie_by_settlement = {t.settlement_id: t for t in tie_outs}

    claimed: set[str] = set()
    results: list[MatchResult] = []

    for invoice in data.invoices:
        result = _match_t0(invoice, index, tie_by_settlement, claimed)
        if result is None:
            result = _match_t1(invoice, index, tie_by_settlement, claimed, tolerance_paise)
        if result is None:
            result = _unmatched(invoice)
        results.append(result)

    return ReconOutput(matches=results, tie_outs=tie_outs)


def _build_index(data: ReconInput) -> _Index:
    by_receipt: dict[str, list[SettlementLeg]] = defaultdict(list)
    by_order: dict[str, list[SettlementLeg]] = defaultdict(list)
    by_settlement: dict[str, list[SettlementLeg]] = defaultdict(list)
    utr_by_settlement: dict[str, str] = {}

    for leg in data.legs:
        if leg.type is not LegType.PAYMENT:
            continue
        if leg.order_receipt:
            by_receipt[leg.order_receipt].append(leg)
        if leg.order_id:
            by_order[leg.order_id].append(leg)
        by_settlement[leg.settlement_id].append(leg)
        utr_by_settlement.setdefault(leg.settlement_id, leg.settlement_utr)

    # UTR → primary credit. A repeated UTR is a double submission, not an unusable
    # ambiguity — see index_credits_by_utr.
    credit_by_utr, duplicate_credits = index_credits_by_utr(data.credits)

    unclaimed = [
        leg
        for leg in data.legs
        if leg.type is LegType.PAYMENT and not leg.order_receipt and not leg.order_id
    ]

    return _Index(
        legs_by_receipt=dict(by_receipt),
        legs_by_order=dict(by_order),
        legs_by_settlement=dict(by_settlement),
        credit_by_utr=credit_by_utr,
        duplicate_credits=duplicate_credits,
        utr_by_settlement=utr_by_settlement,
        unclaimed=unclaimed,
    )


# ---------------------------------------------------------------------------
# T0 — exact reference, unique both ways. Proves nothing. Say so.
# ---------------------------------------------------------------------------
def _match_t0(
    invoice: Invoice,
    index: _Index,
    tie_by_settlement: dict[str, TieOut],
    claimed: set[str],
) -> MatchResult | None:
    legs = index.legs_by_receipt.get(invoice.invoice_id)
    via = "order_receipt"
    if not legs and invoice.order_id:
        legs = index.legs_by_order.get(invoice.order_id)
        via = "order_id"
    if not legs:
        return None

    legs = [x for x in legs if x.entity_id not in claimed]
    if not legs:
        return None

    # Unique BOTH ways: these legs must not also point at another invoice.
    receipts = {x.order_receipt for x in legs if x.order_receipt}
    if len(receipts) > 1:
        return None

    settlement_ids = {x.settlement_id for x in legs}
    if len(settlement_ids) != 1:
        # Legs for one invoice spread across settlements is a T3 structural case.
        return None
    settlement_id = next(iter(settlement_ids))

    utr = index.utr_by_settlement.get(settlement_id, "")
    credit = index.credit_by_utr.get(utr)
    if credit is None:
        # Reference resolves, but the money cannot be located in the bank statement.
        # That is not a three-way match, and calling it one would be the whole problem.
        return None

    settled = [x for x in legs if x.settled]
    if not settled:
        return None

    covered = Paise(sum(int(x.credit) for x in settled))
    residual = Paise(int(invoice.amount_paise) - int(covered))
    for leg in settled:
        claimed.add(leg.entity_id)

    return MatchResult(
        ledger_ref=invoice.invoice_id,
        settlement_refs=[x.entity_id for x in settled],
        bank_refs=[credit.statement_line_id],
        tier=MatchTier.T0_EXACT,
        confidence=1.0,
        residual_paise=residual,
        explanation=(
            f"{via} {invoice.invoice_id} → {len(settled)} leg(s) in {settlement_id}; "
            f"UTR {utr} → bank {credit.statement_line_id}; "
            f"invoice {format_inr(invoice.amount_paise)} vs settled {format_inr(covered)}"
            + (f", residual {format_inr(residual)}" if int(residual) else ", exact")
        ),
        matched=True,
    )


# ---------------------------------------------------------------------------
# T1 — deterministic: amount + date + payer, within tolerance
# ---------------------------------------------------------------------------
def _match_t1(
    invoice: Invoice,
    index: _Index,
    tie_by_settlement: dict[str, TieOut],
    claimed: set[str],
    tolerance_paise: int,
) -> MatchResult | None:
    """No usable reference survived, so match on amount, date and payer instead.

    The amount is a HARD constraint. Date and payer narrow the field; they never widen it.
    """
    window_lo = invoice.issued_at.date()
    candidates = [
        leg
        for leg in index.unclaimed
        if leg.entity_id not in claimed
        and leg.settled
        and abs(int(leg.credit) - int(invoice.amount_paise)) <= tolerance_paise
        and leg.settled_at is not None
        and 0 <= (leg.settled_at.date() - window_lo).days <= T1_WINDOW_DAYS
    ]

    if not candidates:
        return None

    # Ambiguity rule: two equally plausible allocations means we do NOT pick one.
    if len(candidates) > 1:
        best = min(abs(int(x.credit) - int(invoice.amount_paise)) for x in candidates)
        tied = [x for x in candidates if abs(int(x.credit) - int(invoice.amount_paise)) == best]
        if len(tied) > 1:
            return None
        candidates = tied

    leg = candidates[0]
    utr = index.utr_by_settlement.get(leg.settlement_id, "")
    credit = index.credit_by_utr.get(utr)
    if credit is None:
        return None

    residual = Paise(int(invoice.amount_paise) - int(leg.credit))
    claimed.add(leg.entity_id)
    delta_days = (leg.settled_at.date() - window_lo).days if leg.settled_at else 0

    return MatchResult(
        ledger_ref=invoice.invoice_id,
        settlement_refs=[leg.entity_id],
        bank_refs=[credit.statement_line_id],
        tier=MatchTier.T1_DETERMINISTIC,
        confidence=0.9,
        residual_paise=residual,
        explanation=(
            f"no reference survived; amount {format_inr(invoice.amount_paise)} matched leg "
            f"{leg.entity_id} within {format_inr(Paise(tolerance_paise))} at T+{delta_days}; "
            f"UTR {utr} → bank {credit.statement_line_id}"
        ),
        matched=True,
    )


def _unmatched(invoice: Invoice) -> MatchResult:
    """An honest miss. Carries the full invoice amount as its residual.

    Phase 3 classifies these into the 11 exception classes; T2–T4 will recover most of
    them. Until then every one shows up in the exception list, which is where a record we
    could not resolve belongs.
    """
    return MatchResult(
        ledger_ref=invoice.invoice_id,
        settlement_refs=[],
        bank_refs=[],
        tier=MatchTier.T0_EXACT,
        confidence=0.0,
        residual_paise=invoice.amount_paise,
        explanation=(
            f"no exact reference and no unique amount+date candidate for "
            f"{invoice.invoice_id} ({format_inr(invoice.amount_paise)})"
        ),
        matched=False,
    )
