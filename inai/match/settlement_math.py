"""Gross → net tie-out. INAI_SPEC.md §6.1.

    expected_net = Σ(payment.credit)
                 − Σ(payment.fee)              # MDR by method
                 − Σ(payment.tax)              # 18% GST on MDR
                 − Σ(refund.debit)
                 − Σ(dispute.debit)
                 − TCS (marketplace only)
                 + Σ(adjustment.credit)

    residual = bank_credit.amount − expected_net

Runs BEFORE matching. A settlement lands as one lumped NEFT credit covering hundreds of
orders; reconciliation means unpacking that net figure order by order, not matching the
lump sum. This module is the unpacking.

`|residual| ≤ tolerance` → clean. Otherwise the residual is itself a finding, and which
component fails to reconcile decides the exception class in phase 3.

Integer paise throughout. Never float — a rupee-conversion bug in a reconciler is fatal
and embarrassing (INAI_SPEC.md §5.2).
"""

from __future__ import annotations

from collections import defaultdict

from inai.match.types import TieOut
from inai.match.utr import extract_utr
from inai.money import Paise, format_inr
from inai.schema import BankCredit, LegType, SettlementLeg

#: Attribution labels. These become exception classes in phase 3.
SHORT_SETTLEMENT = "short_settlement"
FEE_TAX_VARIANCE = "fee_tax_variance"
MISSING_REFUND_REVERSAL = "missing_refund_reversal"
UNSETTLED_CAPTURE = "unsettled_capture"
DISPUTE_HOLD = "dispute_hold"
EXCESS_CREDIT = "excess_credit"


def tie_out(
    legs: list[SettlementLeg],
    credits: list[BankCredit],
    tolerance_paise: int = 100,
    tcs_by_settlement: dict[str, Paise] | None = None,
) -> list[TieOut]:
    """One tie-out per settlement, paise-exact."""
    by_settlement: dict[str, list[SettlementLeg]] = defaultdict(list)
    for leg in legs:
        by_settlement[leg.settlement_id].append(leg)

    credit_by_utr, _duplicates = index_credits_by_utr(credits)
    tcs = tcs_by_settlement or {}

    out: list[TieOut] = []
    for settlement_id in sorted(by_settlement):
        group = by_settlement[settlement_id]
        out.append(
            _tie_out_one(
                settlement_id=settlement_id,
                legs=group,
                credit=credit_by_utr.get(group[0].settlement_utr),
                tolerance_paise=tolerance_paise,
                tcs_paise=tcs.get(settlement_id, Paise(0)),
            )
        )
    return out


def index_credits_by_utr(
    credits: list[BankCredit],
) -> tuple[dict[str, BankCredit], dict[str, list[BankCredit]]]:
    """UTR → (primary credit, later duplicates).

    A UTR appearing twice is a **double submission**, not an unusable ambiguity. Dropping
    the pair — the obvious first move — is wrong twice over: it makes the original credit
    unfindable, so every invoice in that settlement goes unmatched, AND it hides the
    duplicate payment that is itself a finding worth rupees (`DUPLICATE_PAYMENT`, §2).

    The earliest value date is the settlement; anything identical arriving later is the
    re-submission. That is a real-world rule, not a convenience — and it does not depend on
    our own id-naming, which a matcher must never rely on.
    """
    seen: dict[str, list[BankCredit]] = defaultdict(list)
    for credit in credits:
        utr = credit.extracted_utr or extract_utr(credit.narration)
        if utr:
            seen[utr].append(credit)

    primary: dict[str, BankCredit] = {}
    duplicates: dict[str, list[BankCredit]] = {}
    for utr, group in seen.items():
        ordered = sorted(group, key=lambda c: (c.value_date, c.statement_line_id))
        primary[utr] = ordered[0]
        if len(ordered) > 1:
            duplicates[utr] = ordered[1:]
    return primary, duplicates


def _tie_out_one(
    *,
    settlement_id: str,
    legs: list[SettlementLeg],
    credit: BankCredit | None,
    tolerance_paise: int,
    tcs_paise: Paise,
) -> TieOut:
    gross = fee = tax = refund = dispute = adjustment = 0
    unsettled = 0

    for leg in legs:
        if leg.type is LegType.PAYMENT:
            if leg.settled:
                gross += int(leg.credit)
                fee += int(leg.fee)
                tax += int(leg.tax)
            else:
                # Captured but never settled: the gateway holds it, so it is not part of
                # this credit at all. Tracked separately so it can be attributed.
                unsettled += int(leg.credit) - int(leg.fee) - int(leg.tax)
        elif leg.type is LegType.REFUND:
            refund += int(leg.debit)
        elif leg.type is LegType.DISPUTE:
            dispute += int(leg.debit)
        elif leg.type is LegType.ADJUSTMENT:
            adjustment += int(leg.credit) - int(leg.debit)

    expected_net = gross - fee - tax - refund - dispute - int(tcs_paise) + adjustment
    observed_net = int(credit.amount_paise) if credit is not None else 0
    residual = observed_net - expected_net

    clean = abs(residual) <= tolerance_paise
    attributed = (
        None
        if clean
        else _attribute(
            residual=residual,
            refund=refund,
            dispute=dispute,
            unsettled=unsettled,
            fee=fee,
            tax=tax,
            credit_present=credit is not None,
        )
    )

    return TieOut(
        settlement_id=settlement_id,
        utr=legs[0].settlement_utr,
        bank_ref=credit.statement_line_id if credit else None,
        gross_paise=Paise(gross),
        fee_paise=Paise(fee),
        tax_paise=Paise(tax),
        refund_paise=Paise(refund),
        dispute_paise=Paise(dispute),
        adjustment_paise=Paise(adjustment),
        tcs_paise=tcs_paise,
        expected_net_paise=Paise(expected_net),
        observed_net_paise=Paise(observed_net),
        residual_paise=Paise(residual),
        clean=clean,
        attributed_to=attributed,
        explanation=_explain(
            settlement_id=settlement_id,
            n_legs=len(legs),
            gross=gross,
            fee=fee,
            tax=tax,
            refund=refund,
            dispute=dispute,
            expected_net=expected_net,
            observed_net=observed_net,
            residual=residual,
            clean=clean,
            attributed=attributed,
            credit_present=credit is not None,
        ),
    )


def _attribute(
    *,
    residual: int,
    refund: int,
    dispute: int,
    unsettled: int,
    fee: int,
    tax: int,
    credit_present: bool,
) -> str:
    """Name the component that fails to reconcile.

    Deliberately conservative and ordered by how *identifiable* each cause is. Where the
    residual matches a known component to the paisa, that component is named; otherwise it
    falls through to the honest catch-alls. Guessing here would mean mis-routing money to
    the wrong recovery action.
    """
    if not credit_present:
        return UNSETTLED_CAPTURE

    # Exact-value attributions first. A residual equal to the refund total means the refund
    # was debited from the merchant and never credited back — real money, and invisible
    # without reconciliation.
    if refund and residual == refund:
        return MISSING_REFUND_REVERSAL
    if dispute and residual == dispute:
        return DISPUTE_HOLD
    if unsettled and abs(residual + unsettled) <= 1:
        return UNSETTLED_CAPTURE

    # A residual within the size of the deduction is a fee/tax discrepancy; anything larger
    # is the gateway paying less than computed.
    if residual != 0 and abs(residual) <= (fee + tax):
        return FEE_TAX_VARIANCE
    if residual < 0:
        return SHORT_SETTLEMENT
    return EXCESS_CREDIT


def _explain(
    *,
    settlement_id: str,
    n_legs: int,
    gross: int,
    fee: int,
    tax: int,
    refund: int,
    dispute: int,
    expected_net: int,
    observed_net: int,
    residual: int,
    clean: bool,
    attributed: str | None,
    credit_present: bool,
) -> str:
    """One line a human can check in five seconds. INAI_SPEC.md §6.3."""
    head = (
        f"{settlement_id}: {n_legs} legs, gross {format_inr(Paise(gross))} "
        f"− MDR {format_inr(Paise(fee))} − GST {format_inr(Paise(tax))}"
    )
    if refund:
        head += f" − refunds {format_inr(Paise(refund))}"
    if dispute:
        head += f" − disputes {format_inr(Paise(dispute))}"
    head += f" = expected {format_inr(Paise(expected_net))}"

    if not credit_present:
        return f"{head}; no bank credit found for this UTR"
    head += f", bank credit {format_inr(Paise(observed_net))}"
    if clean:
        return f"{head} — ties out"
    return f"{head} — residual {format_inr(Paise(residual))} attributed to {attributed}"
