"""Contracts. INAI_SPEC.md §5. DuckDB tables mirror these 1:1.

Deviation from the spec text, deliberate: every monetary field is `Paise` (int), including
the ledger and bank sides which §5.1/§5.3 wrote as `Decimal`. Mixing units across the three
sides of a three-way reconciliation is precisely the class of bug §5.2 warns about.
Decimal survives only at the IO boundary (`inai.money`).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from inai.money import Paise


class Frozen(BaseModel):
    """Immutable by default. A reconciler that mutates its inputs cannot be audited."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# §5.1 Ledger side
# ---------------------------------------------------------------------------
class InvoiceStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    PARTIAL = "partial"
    WRITTEN_OFF = "written_off"
    DISPUTED = "disputed"


class Invoice(Frozen):
    invoice_id: str
    customer_id: str
    issued_at: datetime
    due_at: datetime
    amount_paise: Paise
    currency: str = "INR"
    order_id: str | None = None  # joins to settlement order_id
    subscription_id: str | None = None
    status: InvoiceStatus = InvoiceStatus.OPEN
    has_written_agreement: bool = True  # MSME appointed day: 45 days vs 15


# ---------------------------------------------------------------------------
# §5.2 Settlement side — mirrors Razorpay's real report schema (DATA.md §1.1)
# ---------------------------------------------------------------------------
class LegType(StrEnum):
    PAYMENT = "payment"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"
    DISPUTE = "dispute"
    TRANSFER = "transfer"


class Method(StrEnum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMANDATE = "emandate"


class SettlementLeg(Frozen):
    entity_id: str  # pay_… / rfnd_… / adj_… / disp_…
    type: LegType
    debit: Paise
    credit: Paise
    amount: Paise
    currency: str = "INR"
    fee: Paise  # MDR
    tax: Paise  # 18% GST on MDR
    on_hold: bool = False
    settled: bool
    created_at: datetime
    settled_at: datetime | None = None
    settlement_id: str  # setl_…
    settlement_utr: str  # <- THE JOIN KEY into the bank statement
    order_id: str | None = None
    order_receipt: str | None = None
    method: Method
    card_network: str | None = None
    card_issuer: str | None = None
    card_type: str | None = None
    dispute_id: str | None = None


# ---------------------------------------------------------------------------
# §5.3 Bank side
# ---------------------------------------------------------------------------
class BankCredit(Frozen):
    statement_line_id: str
    value_date: date
    amount_paise: Paise
    narration: str  # "NEFT-<UTR>-RAZORPAY SOFTWARE PVT-…" (possibly mangled)
    extracted_utr: str | None = None  # regex first, LLM only if regex fails
    counterparty_guess: str | None = None


# ---------------------------------------------------------------------------
# §5.4 Matching
# ---------------------------------------------------------------------------
class MatchTier(StrEnum):
    T0_EXACT = "t0_exact"  # unique UTR / order_id — proves nothing, say so
    T1_DETERMINISTIC = "t1_deterministic"  # amount + date + payer within tolerance
    T2_FUZZY = "t2_fuzzy"  # mangled narration, name similarity — the real score
    T3_STRUCTURAL = "t3_structural"  # bundled / split / partial
    T4_ADVERSARIAL = "t4_adversarial"  # parent-co payer, unexplained deduction, duplicate


TIER_ORDER: tuple[MatchTier, ...] = (
    MatchTier.T0_EXACT,
    MatchTier.T1_DETERMINISTIC,
    MatchTier.T2_FUZZY,
    MatchTier.T3_STRUCTURAL,
    MatchTier.T4_ADVERSARIAL,
)


class MatchResult(Frozen):
    ledger_ref: str
    settlement_refs: list[str] = Field(default_factory=list)
    bank_refs: list[str] = Field(default_factory=list)
    tier: MatchTier
    confidence: float = Field(ge=0.0, le=1.0)
    residual_paise: Paise  # unexplained amount after fee/tax math
    explanation: str  # a human must be able to check this in five seconds
    matched: bool


# ---------------------------------------------------------------------------
# §5.5 Exceptions and decisions
# ---------------------------------------------------------------------------
class ExceptionClass(StrEnum):
    UNAPPLIED_CASH = "UNAPPLIED_CASH"
    GENUINELY_UNPAID = "GENUINELY_UNPAID"
    SHORT_SETTLEMENT = "SHORT_SETTLEMENT"
    MISSING_REFUND_REVERSAL = "MISSING_REFUND_REVERSAL"
    UNSETTLED_CAPTURE = "UNSETTLED_CAPTURE"
    PARTIAL_PAYMENT = "PARTIAL_PAYMENT"
    FEE_TAX_VARIANCE = "FEE_TAX_VARIANCE"
    DUPLICATE_PAYMENT = "DUPLICATE_PAYMENT"
    TIMING_DIFFERENCE = "TIMING_DIFFERENCE"
    DISPUTE_HOLD = "DISPUTE_HOLD"
    UNRESOLVED = "UNRESOLVED"


#: Classes whose rupees are clawed back from the payment rails rather than from a customer.
#: Feeds `rails_leakage_recovered_inr` (§9.4).
RAILS_LEAKAGE_CLASSES: frozenset[ExceptionClass] = frozenset(
    {
        ExceptionClass.SHORT_SETTLEMENT,
        ExceptionClass.MISSING_REFUND_REVERSAL,
        ExceptionClass.UNSETTLED_CAPTURE,
        ExceptionClass.FEE_TAX_VARIANCE,
    }
)


class ActionType(StrEnum):
    AUTO_APPLY = "auto_apply"
    CANCEL_DUNNING = "cancel_dunning"
    SUSPEND_DUNNING = "suspend_dunning"
    SILENT_RETRY = "silent_retry"
    UPI_COLLECT = "upi_collect"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    EMAIL = "email"
    VOICE = "voice"
    HUMAN_QUEUE = "human_queue"
    REAUTH_LINK = "reauth_link"
    PG_ADJUSTMENT_QUERY = "pg_adjustment_query"
    CREDIT_NOTE = "credit_note"
    WRITE_OFF = "write_off"
    NO_ACTION = "no_action"


class Exception_(Frozen):
    exception_id: str
    cls: ExceptionClass
    ledger_ref: str | None = None
    settlement_refs: list[str] = Field(default_factory=list)
    bank_refs: list[str] = Field(default_factory=list)
    amount_paise: Paise
    machine_reason: str
    human_reason: str = ""  # LLM-written, one line, replay-cached
    routed_action: ActionType | None = None


class Arm(StrEnum):
    AGENT = "agent"  # 70% — full pipeline
    CONTROL = "control"  # 20% — naive baseline, NO reconciliation
    PURE_HOLDOUT = "pure_holdout"  # 10% — no action, measures true self-cure


class Retryability(StrEnum):
    RETRY_NOW = "retry_now"
    RETRY_TIMED = "retry_timed"
    RETRY_AFTER_HEALTH = "retry_after_health"
    NO_RETRY = "no_retry"
    UNKNOWN = "unknown"


class RootCause(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    ISSUER_DOWN = "issuer_down"
    MANDATE_REVOKED = "mandate_revoked"
    CARD_EXPIRED = "card_expired"
    AMOUNT_EXCEEDS_MANDATE = "amount_exceeds_mandate"
    TECHNICAL_TRANSIENT = "technical_transient"
    ACCOUNT_CLOSED = "account_closed"
    UNKNOWN = "unknown"


class Diagnosis(Frozen):
    root_cause: RootCause
    retryability: Retryability
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "taxonomy" | "llm" — never silently mixed


class Candidate(Frozen):
    action: ActionType
    tau: float  # P(recover | do(a)) - P(recover | do(nothing))
    ev_paise: Paise
    cost_paise: Paise
    annoyance: float
    scheduled_for: datetime | None = None
    rejected_reason: str | None = None


class GateVerdict(Frozen):
    allowed: bool
    rule_id: str | None = None  # POL-*
    rule_text: str | None = None
    remediation: str | None = None


class Outcome(StrEnum):
    RECOVERED = "recovered"
    FAILED = "failed"
    PENDING = "pending"
    SUPPRESSED = "suppressed"
    WRITTEN_OFF = "written_off"
    DUNNING_CANCELLED = "dunning_cancelled"


class Decision(Frozen):
    decision_id: str
    run_id: str
    account_id: str
    ts: datetime
    arm: Arm
    source_exception: str | None = None
    diagnosis: Diagnosis | None = None
    #: ALL scored options, including the rejected ones. Showing a judge what the agent
    #: chose *not* to do is what makes it legible as an agent rather than a workflow.
    candidates: list[Candidate] = Field(default_factory=list)
    chosen: Candidate | None = None
    gate: GateVerdict
    executed: bool = False
    outcome: Outcome | None = None
    amount_recovered_paise: Paise = Paise(0)
    cost_incurred_paise: Paise = Paise(0)
    cost_avoided_paise: Paise = Paise(0)  # false dunning prevented, futile retries avoided
