"""Forward generation. DATA.md §5, STEP 1 and STEP 2.

    STEP 1  invoice → order → payment(s) → settlement leg(s) → bank credit
            Every link known by construction. The match answer is free AND provably correct.

    STEP 2  gross − MDR − GST(MDR) − TCS ± refunds ± disputes + adjustments = net credit
            Paise-exact. This is the arithmetic the matcher must later rediscover.

Because truth precedes corruption, ground truth is correct by construction — no labelling,
no annotator disagreement, no "we eyeballed 200 rows".

Nothing in here may be imported by `inai/match/**` or `inai/core/**`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from inai.config import ResolvedConfig
from inai.money import Paise
from inai.schema import (
    BankCredit,
    Invoice,
    InvoiceStatus,
    LegType,
    Method,
    SettlementLeg,
)
from inai.sim.chain import Batch, LedgerChain, Settlement
from inai.sim.localize import AmountScaler, localize_method
from inai.sim.narration import (
    direct_narration,
    make_utr,
    payer_name,
    settlement_narration,
)
from inai.sim.spine import SpineOrder, load_spine
from inai.sim.truth import LATENT_STATE_PRIOR, LatentState

#: MDR is quoted per method (INAI_SPEC.md §3.1). UPI is mandated 0%.
_MDR_KEY: dict[Method, str] = {
    Method.UPI: "mdr.upi_pct",
    Method.CARD: "mdr.debit_card_pct",
    Method.NETBANKING: "mdr.netbanking_pct",
    Method.WALLET: "mdr.wallet_pct",
    Method.EMANDATE: "mdr.debit_card_pct",
}

_CARD_NETWORKS = ("Visa", "MasterCard", "RuPay", "Amex")
_CARD_ISSUERS = ("HDFC Bank", "ICICI Bank", "SBI", "Axis Bank", "Kotak", "IndusInd")


def _pct_of(amount: Paise, pct: float) -> Paise:
    """Percentage of a paise amount, rounded half-up to whole paise.

    Integer arithmetic throughout: a float here is how a reconciler ends up one paisa out
    on a settlement of four hundred orders and can never explain the residual.
    """
    return Paise((int(amount) * round(pct * 10_000) + 500_000) // 1_000_000)


def generate(cfg: ResolvedConfig, rng: np.random.Generator) -> Batch:
    """Generate one uncorrupted batch. Corruption is applied afterwards, by `corrupt`."""
    n = cfg.run.n_records
    orders = load_spine(n_orders=n, seed=cfg.run.seed, repeat_boost=float(cfg.run.repeat_boost))

    scaler = AmountScaler(
        values=[p.value for o in orders for p in o.payments],
        median_inr=float(cfg.run.median_ticket_inr),
        sigma=float(cfg.run.amount_sigma),
    )

    rng_amount, rng_method, rng_time, rng_state, rng_utr, rng_channel = rng.spawn(6)

    # Compress the spine's two-year span into one operating window.
    #
    # Without this the settlement structure is wrong in the way that matters most: keyed by
    # value date, 200 orders spread over Sep 2016 – Oct 2018 produce ~168 settlements of
    # roughly one order each. The entire problem statement is that "a settlement arrives as
    # a single lumped NEFT credit covering hundreds of orders" (DATA.md §1.3) — a generator
    # that emits one order per credit reproduces none of the difficulty.
    #
    # Rank-preserving, so order sequence and relative density survive.
    clock = _TimelineCompressor(
        [o.purchase_at for o in orders], window_days=int(cfg.run.window_days)
    )

    chains: list[LedgerChain] = []
    settlements: dict[str, Settlement] = {}

    # The channel is a property of the CUSTOMER, not of the individual invoice.
    #
    # A B2B customer who pays by NEFT pays by NEFT every time; a consumer checking out on
    # the website goes through the gateway every time. Drawing per-invoice instead scattered
    # both channels through one customer's history, which is not how anyone pays — and it
    # made C02 (a customer settling several open invoices with one transfer) almost
    # impossible, because it needs two DIRECT invoices from the same payer.
    channel_of: dict[str, bool] = {}

    gst_pct = float(cfg.constant("tax.gst_on_mdr_pct"))
    cycle_min = int(cfg.constant("settlement.cycle_days_min"))
    cycle_max = int(cfg.constant("settlement.cycle_days_max"))

    for idx, order in enumerate(orders):
        chain = _build_chain(
            idx=idx,
            order=order,
            clock=clock,
            cfg=cfg,
            scaler=scaler,
            gst_pct=gst_pct,
            cycle_min=cycle_min,
            cycle_max=cycle_max,
            settlements=settlements,
            rng_amount=rng_amount,
            rng_method=rng_method,
            rng_time=rng_time,
            rng_state=rng_state,
            rng_utr=rng_utr,
            direct=channel_of.setdefault(
                order.customer_id,
                bool(rng_channel.random() < float(cfg.run.direct_payment_share)),
            ),
        )
        if chain is not None:
            chains.append(chain)

    credits = _settle(settlements, chains, rng_utr)
    credits += _direct_credits(chains, rng_utr)
    return Batch(chains=chains, settlements=settlements, credits=credits)


def _build_chain(
    *,
    idx: int,
    order: SpineOrder,
    clock: _TimelineCompressor,
    cfg: ResolvedConfig,
    scaler: AmountScaler,
    gst_pct: float,
    cycle_min: int,
    cycle_max: int,
    settlements: dict[str, Settlement],
    rng_amount: np.random.Generator,
    rng_method: np.random.Generator,
    rng_time: np.random.Generator,
    rng_state: np.random.Generator,
    rng_utr: np.random.Generator,
    direct: bool = False,
) -> LedgerChain | None:
    issued_at = clock.map(order.purchase_at)
    due_at = issued_at + timedelta(days=int(rng_time.integers(7, 45)))

    total = Paise(sum(int(scaler.to_paise(p.value)) for p in order.payments))
    if total <= 0:
        return None

    invoice = Invoice(
        invoice_id=f"inv_{idx:07d}",
        customer_id=f"cus_{order.customer_id[:12]}",
        customer_name=payer_name(order.customer_id),
        issued_at=issued_at,
        due_at=due_at,
        amount_paise=total,
        order_id=f"order_{order.order_id[:14]}",
        status=InvoiceStatus.PAID if not order.cancelled else InvoiceStatus.OPEN,
        # Drives MSME appointed day: 45 days vs 15. Most B2B has paper; some does not.
        has_written_agreement=bool(rng_state.random() < 0.78),
    )

    if direct:
        # No gateway, so no legs, no MDR, no GST — the customer's bank moves the full
        # amount into the merchant's account and the reconciliation is ledger × bank only.
        # A two-way match is not a lesser case: it is most of B2B receivables.
        return LedgerChain(
            invoice=invoice,
            legs=[],
            settlement_id=None,
            channel="direct",
            latent_state=_draw_latent(rng_state),
        )

    # Settlement cycle T+1…T+7, one cycle per (value_date), shared across many orders —
    # this is what makes the credit "lumped" rather than one-credit-per-order.
    settled_at = issued_at + timedelta(days=int(rng_time.integers(cycle_min, cycle_max + 1)))
    value_date = settled_at.date()
    settlement_id = f"setl_{value_date.strftime('%y%m%d')}"
    settlement = settlements.get(settlement_id)
    if settlement is None:
        settlement = Settlement(
            settlement_id=settlement_id,
            utr=make_utr(rng_utr, value_date),
            value_date=value_date,
        )
        settlements[settlement_id] = settlement

    legs: list[SettlementLeg] = []
    for p in order.payments:
        amount = scaler.to_paise(p.value)
        if int(amount) <= 0:
            continue
        method = localize_method(p.payment_type, rng_method)
        fee = _pct_of(amount, float(cfg.constant(_MDR_KEY[method])))
        tax = _pct_of(fee, gst_pct)
        is_card = method in (Method.CARD, Method.EMANDATE)
        leg = SettlementLeg(
            entity_id=f"pay_{idx:07d}{p.sequential:02d}",
            type=LegType.PAYMENT,
            debit=Paise(0),
            credit=amount,
            amount=amount,
            fee=fee,
            tax=tax,
            settled=True,
            created_at=issued_at,
            settled_at=settled_at,
            settlement_id=settlement_id,
            settlement_utr=settlement.utr,
            order_id=invoice.order_id,
            order_receipt=invoice.invoice_id,
            method=method,
            card_network=_CARD_NETWORKS[int(rng_method.integers(0, len(_CARD_NETWORKS)))]
            if is_card
            else None,
            card_issuer=_CARD_ISSUERS[int(rng_method.integers(0, len(_CARD_ISSUERS)))]
            if is_card
            else None,
            card_type="credit"
            if is_card and rng_method.random() < 0.6
            else ("debit" if is_card else None),
        )
        legs.append(leg)
        settlement.legs.append(leg)

    if not legs:
        return None

    return LedgerChain(
        invoice=invoice,
        legs=legs,
        settlement_id=settlement_id,
        channel="gateway",
        latent_state=_draw_latent(rng_state),
    )


def _draw_latent(rng: np.random.Generator) -> LatentState:
    states = list(LATENT_STATE_PRIOR)
    weights = np.array([LATENT_STATE_PRIOR[s] for s in states])
    return states[int(rng.choice(len(states), p=weights / weights.sum()))]


def _direct_credits(chains: list[LedgerChain], rng: np.random.Generator) -> list[BankCredit]:
    """One bank line per direct payment.

    Deliberately NOT lumped: a customer's own transfer arrives as its own statement line,
    which is exactly why direct payments are the tractable half of the problem — right up
    until the reference is missing or the money comes from the wrong account.
    """
    out: list[BankCredit] = []
    for i, chain in enumerate(chains):
        if chain.channel != "direct":
            continue
        value_date = (chain.invoice.due_at - timedelta(days=int(rng.integers(0, 6)))).date()
        narration, _ref = direct_narration(
            rng,
            customer_name=chain.invoice.customer_name,
            invoice_id=chain.invoice.invoice_id,
            amount_paise=int(chain.invoice.amount_paise),
            value_date=value_date,
            include_reference=True,
        )
        line_id = f"dir_{i:07d}"
        out.append(
            BankCredit(
                statement_line_id=line_id,
                value_date=value_date,
                amount_paise=chain.invoice.amount_paise,
                narration=narration,
                counterparty_guess=None,
            )
        )
        chain.bank_ref = line_id
    return out


def _settle(
    settlements: dict[str, Settlement],
    chains: list[LedgerChain],
    rng: np.random.Generator,
) -> list[BankCredit]:
    """One lumped bank credit per settlement — net of MDR, GST and adjustments.

    `expected_net` is computed from the legs, so the credit and the legs are consistent by
    construction. Corruption operators later break that consistency in documented ways, and
    the residual they leave behind is what Stage 1 has to explain.
    """
    credits: list[BankCredit] = []
    for settlement_id, s in sorted(settlements.items()):
        net = s.expected_net()
        if int(net) <= 0:
            continue
        line_id = f"stmt_{settlement_id[5:]}"
        credits.append(
            BankCredit(
                statement_line_id=line_id,
                value_date=s.value_date,
                amount_paise=net,
                narration=settlement_narration(rng, s.utr, s.value_date, int(net)),
                extracted_utr=None,  # Stage 1's job, not the generator's
                counterparty_guess=None,
            )
        )
        for chain in chains:
            if chain.settlement_id == settlement_id:
                chain.bank_ref = line_id
    return credits


def settlement_of(batch: Batch, chain: LedgerChain) -> Settlement | None:
    return batch.settlements.get(chain.settlement_id) if chain.settlement_id else None


def utc_now() -> datetime:
    return datetime.now(UTC)


class _TimelineCompressor:
    """Map the spine's real timestamps onto a recent operating window, preserving order.

    A merchant reconciling a month of trading is the scenario; a merchant reconciling two
    years in one batch is not. Compressing is what makes settlements lump.
    """

    def __init__(self, timestamps: list[datetime], window_days: int) -> None:
        clean = sorted(t for t in timestamps if t is not None)
        self._lo = clean[0] if clean else datetime(2018, 1, 1)
        self._hi = clean[-1] if clean else datetime(2018, 12, 31)
        self._span = max((self._hi - self._lo).total_seconds(), 1.0)
        self._window = float(window_days * 86_400)
        # Anchored to a fixed date, not to "now": a run must not change because the clock did.
        self._end = datetime(2026, 7, 31, tzinfo=UTC)

    def map(self, ts: datetime) -> datetime:
        naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
        frac = (naive - self._lo).total_seconds() / self._span
        frac = min(max(frac, 0.0), 1.0)
        return self._end - timedelta(seconds=self._window * (1.0 - frac))
