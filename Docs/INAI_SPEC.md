# INAI · இணை

**Match first. Then chase.**

Razorpay AI Buildathon — one agent, one loop, both tracks.
Track 03 (AI Revenue Recovery) + Track 04 (AI Finance Controller).

> *iṇai* (இணை, Tamil) — to match, to pair, to join.
> Wordmark: **INAI** · Descriptor: *Reconciliation-first revenue recovery*

Companion document: **`DATA.md`** — data sources, generator design, corruption operators,
ground-truth contract. Read it before writing any code in `inai/sim/` or `inai/match/`.

---

## 0. How to use this document

Executable specification. Read fully before implementing.

1. Build in the phase order in §11. Each phase has acceptance criteria. Do not advance until they pass.
2. Every constant in §3 is sourced. Do not invent numbers. New constants go in
   `config/constants.yaml` with `source:` and `verify:` fields.
3. `[VERIFY]` = a regulatory or schema fact that moves. Check live before demo day.
4. The measurement harness (§9) is the product, not a reporting layer. Cut anything else first.
5. Determinism: `(seed, config_hash) → identical scorecard`. No unseeded `random`. No LLM on a
   scoring, matching-decision, or policy path.
6. Ground truth lives in `inai/sim/truth.py` and **must never be importable from `inai/core/**`
   or `inai/match/**`**. CI enforces this.

---

## 1. Thesis

### 1.1 The two tracks are one loop

Track 03: find revenue slipping away, intervene, recover it, prove the money.
Track 04: close a finance-ops loop over a batch, report match rate and honest exceptions.

The bridge:

> **Revenue at risk is not only revenue that failed to arrive. It is also revenue that arrived and
> was never recognised.** A recovery agent running on an unreconciled ledger spends real money
> chasing customers who already paid.

Therefore: **the reconciliation exception list *is* the revenue-at-risk queue.** One artifact,
two tracks. Remove either half and the product stops working.

### 1.2 Documented, not clever

- Unapplied cash makes paid invoices appear open, so unnecessary collection contacts get made and
  customers land on credit hold for items already settled.
- The tolerance is tight: unapplied cash must stay under **2–3% of total AR**; above that it
  degrades collection effort outright.
- The market has not solved it: only **23%** of businesses have any cash-application automation;
  manual AR carries **30% longer DSO**; **52%** of finance leaders name manual process as their
  single biggest AR weakness.
- Settlement recon is the specific bottleneck where Razorpay's merchants live: past **1,000
  transactions/month**, manual settlement reconciliation is the primary cause of month-end close
  delay; past 800–1,000 entries, teams burn **15–25 hours/month** on it.
- A Razorpay settlement arrives as a single lumped NEFT credit covering hundreds of orders, net of
  MDR, GST on MDR and refund adjustments. Reconciliation means unpacking that net figure **order by
  order**, not matching the lump sum.

### 1.3 Why the recovery benchmarks can't be trusted either

Published dunning recovery rates for the same operation: 50–80%, 42%, 57%, 58%, 20–30%. All gross,
all vendor-published, none with a control group. The one credible figure is stated as a *lift*:
smart retry timing gives roughly **+25% over fixed intervals**.

**Design consequence:** INAI's headline recovery number is incremental — treatment minus randomised
control — with a 95% confidence interval. Its headline recon number is match rate **by difficulty
tier**, not blended.

---

## 2. What INAI does

**Stage 1 — VERIFY.** Three-way match: Razorpay settlement report × bank statement credits ×
merchant ledger (invoices / orders / subscriptions). Output: tiered match rate + classified
exceptions.

**Stage 2 — CLASSIFY.** Every unmatched record gets a class, never a shrug.

**Stage 3 — ACT.** Each class routes to a bounded, policy-gated action.

| Exception class | Reality | Action | Money effect |
|---|---|---|---|
| `UNAPPLIED_CASH` | Paid, unmatched | Auto-apply + **cancel scheduled dunning** | Saves contact cost + churn |
| `GENUINELY_UNPAID` | No payment exists | Recovery ladder (§8) | Recovers |
| `SHORT_SETTLEMENT` | Gateway paid less than computed | Raise adjustment query with PG | Recovers from the rails |
| `MISSING_REFUND_REVERSAL` | Refund debited, never reversed | Claim | Recovers from the rails |
| `UNSETTLED_CAPTURE` | Captured, never settled | Chase settlement | Recovers from the rails |
| `PARTIAL_PAYMENT` | Underpaid | Chase **balance only** | Prevents wrong-amount chase |
| `FEE_TAX_VARIANCE` | MDR/GST/TCS computed ≠ deducted | Dispute or accept within tolerance | Recovers |
| `DUPLICATE_PAYMENT` | Paid twice | Credit note / refund | Prevents dispute |
| `TIMING_DIFFERENCE` | Will settle T+n | Suppress action, revisit | Prevents false dunning |
| `DISPUTE_HOLD` | Chargeback in flight | Freeze, human queue | Prevents illegal chase |
| `UNRESOLVED` | Honest gap | Human queue, displayed | Reported, not hidden |

---

## 3. R&D — calibration constants

Encode as `config/constants.yaml`; every entry carries `value`, `unit`, `source`, `as_of`, `verify`.
Full provenance in `DATA.md` §7 and §13 below.

### 3.1 Settlement & fee economics

| Key | Value | Source |
|---|---|---|
| `mdr.upi_pct` | 0.0 | government mandate |
| `mdr.debit_card_pct` | 1.5–2.0 | practitioner reference |
| `mdr.intl_credit_pct` | 2.5–3.5 | practitioner reference |
| `tax.gst_on_mdr_pct` | 18.0 | ITC-eligible for GST-registered merchants |
| `tax.tcs_marketplace` | applicable | marketplace operators only |
| `settlement.cycle_days` | T+1 … T+7 | varies by gateway and merchant tier |
| `settlement.form` | single lumped NEFT credit per cycle | Razorpay |

### 3.2 Reconciliation

| Key | Value | Source |
|---|---|---|
| `recon.unapplied_cash_tolerance_pct_of_ar` | 2–3 | AR practice; above this, collections degrade |
| `recon.market_automation_rate_pct` | 23 | Blackline B2B AR benchmarking |
| `recon.manual_dso_penalty_pct` | 30 | Blackline |
| `recon.pain_threshold_txn_per_month` | 800–1,000 | field observation |
| `recon.manual_hours_per_month_at_threshold` | 15–25 | field observation |
| `recon.close_delay_threshold_txn_per_month` | 1,000 | practitioner reference |
| `recon.vendor_claimed_match_rate_pct` | 95+ | vendor claim — the bar, not the truth |

### 3.3 Payment failure rates

| Key | Value | Source |
|---|---|---|
| `upi.technical_decline_target_pct` | < 1 | NPCI Circular OC-149 (Jun 2022); TD fell 8–10% (2016) → ~0.8% (2025) |
| `upi.business_decline_target_pct` | < 5 | NPCI OC-149 |
| `subscription.debit_failure_rate_pct` | 10–15 (default 12) | Indian consumer subscription merchants, 2026 |
| `nach.bounce_rate_volume_baseline_pct` | 31.5 | NPCI, Feb 2020 (pre-Covid) |
| `nach.bounce_rate_value_baseline_pct` | 24.9 | NPCI, Feb 2020 |
| `nach.bounce_rate_volume_oct2021_pct` | 31.24 | NPCI (86.6M presented, 27M failed) |
| `nach.bounce_rate_volume_peak_pct` | 45.4 | NPCI, Jun 2020 — stress scenario |
| `card.failure_rate_pct` | ~15 | industry aggregate |
| `ach_dd.failure_rate_pct` | 3–5 | industry aggregate |

`[VERIFY]` Pull the **current month** NACH presentations/returns before demo. Never present 2021
figures as current.

### 3.4 Action costs

| Key | Value | Source |
|---|---|---|
| `cost.nach_bounce_fee_inr` | 350–500 (default 425) | originating-bank charge |
| `cost.sms_inr` | 0.15–0.25 | DLT transactional `[VERIFY]` |
| `cost.whatsapp_utility_inr` | 0.12–0.35 | Meta utility template, India `[VERIFY]` |
| `cost.voice_call_inr` | 5.00 | directional |
| `cost.human_agent_inr` | 90.00 | directional |
| `cost.false_dunning_inr` | contact cost + modelled churn risk | derived, §9.3 |

The bounce fee is the most load-bearing constant in the model. It converts "never retry a revoked
mandate" from a vague efficiency claim into rupees.

### 3.5 Recovery context (pitch only — never simulator ground truth)

| Fact | Value |
|---|---|
| Involuntary share of subscription churn | 20–40%; 40–50% with no retry logic |
| Reminder open rate <24h vs >30d | 41.3% vs 26.8% |
| Smart retry timing lift over fixed intervals | ~25% |
| Payday-aligned charge dates | reduce insufficient-funds failures |

Using these as simulator ground truth would make the evaluation circular. Cite them; don't encode them.

### 3.6 Regulatory

| Key | Value | Verify |
|---|---|---|
| `rbi.pre_debit_notification_hours` | 24 | `[VERIFY]` |
| `rbi.afa_exempt_limit_general_inr` | 15,000 | `[VERIFY]` |
| `rbi.afa_exempt_limit_special_inr` | 100,000 (MF, insurance premia, credit-card bills) | `[VERIFY]` |
| `rbi.optout_required` | true — pre- and post-transaction notification plus opt-out must persist | |
| `rbi.exempt_categories_no_predebit` | FASTag / NCMC auto-replenishment (no fixed periodicity) | |
| `npci.retry_cap_per_cycle` | bounded, not unlimited; PSPs must throttle execution rate | `[VERIFY]` |
| `trai.dlt_template_required` | true | |
| `contact.permitted_hours_ist` | 09:00–18:00 | conservative default |

### 3.7 MSME receivables (P1)

| Key | Value |
|---|---|
| `msme.appointed_day_days` | 45 (15 with no written agreement) |
| `msme.interest_multiple_of_bank_rate` | 3×, compounded with monthly rests (MSMED §16) |
| `msme.rbi_bank_rate_pct` | 5.50 `[VERIFY]` |
| `msme.nominal_rate_pct` | 16.50 |
| `msme.effective_rate_pct` | ≈17.81 — (1 + 0.165/12)^12 − 1 |
| `msme.odr_filing_mandatory_since` | 2025-10-15 |
| `msme.filing_fee_inr` | 0 |

Worked-example check: **₹10,00,000 over three years at a 5.50% bank rate ≈ ₹6,35,000 accrued
interest.** Unit-test against this.

Pitch figures: 256,892 applications worth ₹55,244 cr filed as of 14 Aug 2026; ₹20,979 cr pending;
40,580 (16%) unresolved beyond a year; Economic Survey 2025–26 estimates ~₹8.1 lakh crore locked in
MSME delayed payments. MSME (Amendment) Bill 2026: 90-day mediation, 30-day arbitration referral,
90-day awards, recovery as arrears of land revenue, mandatory TReDS routing for CPSEs.
`[VERIFY commencement — passage ≠ notification into force.]`

---

## 4. Architecture

```
  ledger.csv        settlement_report.json        bank_statement.csv
  (invoices)        (Razorpay schema)             (narrations, UTRs)
       │                     │                            │
       └──────────┬──────────┴────────────┬───────────────┘
                  ▼                        ▼
        ┌────────────────────────────────────────┐
        │  STAGE 1 · MATCHER                     │
        │  T0 exact → T1 deterministic           │
        │  → T2 fuzzy → T3 structural → T4 adv.  │
        │  + SETTLEMENT MATH (gross→net tie-out) │
        └───────────────┬────────────────────────┘
                        │  matched            unmatched
             ┌──────────┘                        │
             ▼                                   ▼
   ledger closed, dunning       ┌────────────────────────────────┐
   CANCELLED  ◀─────────────────│  STAGE 2 · EXCEPTION CLASSIFIER│
   (false-dunning prevented)    │  11 classes (§2)               │
                                └───────────────┬────────────────┘
                                                ▼
                        ┌───────────────────────────────────────┐
                        │  STAGE 3 · RECOVERY CORE              │
                        │   diagnose · inflow timing            │
                        │   issuer health · EV/uplift scorer    │
                        │   POLICY GATE · ladder · PTP          │
                        └───────────────┬───────────────────────┘
                                        │ every decision → append-only DECISION LOG
                        ┌───────────────▼───────────────────────┐
                        │  CHANNELS  ·  OUTCOME RESOLUTION      │
                        └───────────────┬───────────────────────┘
                                        ▼
                        ┌───────────────────────────────────────┐
                        │  MEASUREMENT HARNESS                  │
                        │  match rate by tier · incremental ₹   │
                        │  false dunning prevented · rails ₹    │
                        │  95% CI · exception list              │
                        └───────────────────────────────────────┘
```

Arms run in parallel over the same batch: **AGENT (70%) / CONTROL (20%) / PURE_HOLDOUT (10%)**.

**Stack.** Python 3.11 · Pydantic v2 (all contracts) · Polars (batch) · DuckDB (store) ·
RapidFuzz (T2 matching) · FastAPI · Vite + React + TS + Tailwind + Recharts ·
Anthropic API (`claude-sonnet-4-6`) confined to §8.7 · `typer` CLI.
Everything headless: `inai run --config configs/demo.yaml --seed 42`.

---

## 5. Data model

`inai/schema.py`. DuckDB tables mirror 1:1.

### 5.1 Ledger side

```python
class Invoice(BaseModel):
    invoice_id: str
    customer_id: str
    issued_at: datetime
    due_at: datetime
    amount_inr: Decimal
    currency: str = "INR"
    order_id: str | None            # joins to settlement order_id
    subscription_id: str | None
    status: Literal["open","paid","partial","written_off","disputed"]
    has_written_agreement: bool      # drives MSME appointed-day = 45 vs 15
```

### 5.2 Settlement side — mirror Razorpay's real report schema

```python
class SettlementLeg(BaseModel):
    entity_id: str                   # pay_… / rfnd_… / adj_… / disp_…
    type: Literal["payment","refund","adjustment","dispute","transfer"]
    debit: int                       # paise
    credit: int                      # paise
    amount: int                      # paise
    fee: int                         # paise — MDR
    tax: int                         # paise — GST on MDR
    settled: bool
    settled_at: datetime | None
    settlement_id: str               # setl_…
    settlement_utr: str              # ← THE JOIN KEY into the bank statement
    order_id: str | None
    order_receipt: str | None
    method: str                      # card | upi | netbanking | wallet | emandate
    card_network: str | None
    card_issuer: str | None
    card_type: str | None
    dispute_id: str | None
```

Amounts in **paise**, integer, exactly as Razorpay returns them. Never float. Never rupees
internally. A rupee-conversion bug in a reconciler is fatal and embarrassing.

### 5.3 Bank side

```python
class BankCredit(BaseModel):
    statement_line_id: str
    value_date: date
    amount_inr: Decimal
    narration: str                   # "NEFT-<UTR>-RAZORPAY SOFTWARE PVT-…" (possibly mangled)
    extracted_utr: str | None        # regex first, LLM only if regex fails
    counterparty_guess: str | None
```

### 5.4 Matching

```python
class MatchTier(StrEnum):
    T0_EXACT         = "t0_exact"          # unique UTR / order_id
    T1_DETERMINISTIC = "t1_deterministic"  # amount + date + payer within tolerance
    T2_FUZZY         = "t2_fuzzy"          # mangled narration, name similarity
    T3_STRUCTURAL    = "t3_structural"     # bundled / split / partial
    T4_ADVERSARIAL   = "t4_adversarial"    # parent-co payer, unexplained deduction, duplicate

class MatchResult(BaseModel):
    ledger_ref: str
    settlement_refs: list[str]
    bank_refs: list[str]
    tier: MatchTier
    confidence: float
    residual_inr: Decimal            # unexplained amount after fee/tax math
    explanation: str
    matched: bool
```

### 5.5 Exceptions and decisions

```python
class Exception_(BaseModel):
    exception_id: str
    cls: ExceptionClass              # §2 table
    ledger_ref: str | None
    settlement_refs: list[str]
    bank_refs: list[str]
    amount_inr: Decimal
    machine_reason: str
    human_reason: str                # LLM-written, one line
    routed_action: ActionType | None

class Decision(BaseModel):
    decision_id: str; run_id: str; account_id: str; ts: datetime; arm: Arm
    source_exception: str | None
    diagnosis: Diagnosis | None
    candidates: list[Candidate]      # ALL scored options, including rejected ones
    chosen: Candidate | None
    gate: GateVerdict
    executed: bool
    outcome: Literal["recovered","failed","pending","suppressed","written_off","dunning_cancelled"] | None
    amount_recovered_inr: Decimal
    cost_incurred_inr: Decimal
    cost_avoided_inr: Decimal        # ← false dunning prevented, futile retries avoided
```

`candidates` holding the *rejected* options is not overhead. Showing a judge what the agent chose
not to do, and why, is what makes it legible as an agent rather than a workflow.

---

## 6. Stage 1 — Matcher

`inai/match/`. Deterministic. No LLM in the match decision.

### 6.1 Settlement math — `settlement_math.py`

Before matching, tie gross to net per settlement:

```
expected_net = Σ(payment.credit)
             − Σ(payment.fee)              # MDR by method (§3.1)
             − Σ(payment.tax)              # 18% GST on MDR
             − Σ(refund.debit)
             − Σ(dispute.debit)
             − TCS (marketplace only)
             + Σ(adjustment.credit)

residual = bank_credit.amount − expected_net
```

`|residual| ≤ tolerance` → tie-out clean. Otherwise the residual is itself a finding, classified
into `SHORT_SETTLEMENT` / `FEE_TAX_VARIANCE` / `MISSING_REFUND_REVERSAL` by which component fails
to reconcile. **The residual is the product.** Most "recon tools" stop at match/no-match; INAI
explains the gap in rupees and attributes it.

### 6.2 Tiered matching cascade

Each tier runs only on what the previous tier left unmatched. Record the tier on every match.

- **T0** — `extracted_utr` ↔ `settlement_utr`, or `order_id` ↔ `order_receipt`, unique both ways.
  Should be near 100%. **Say out loud that it proves nothing.**
- **T1** — amount within ±₹1, value_date within settlement window, payer identity consistent.
- **T2** — RapidFuzz token-set ratio on narration vs customer/counterparty name, thresholded, with
  amount as a hard constraint. **This is the real score.**
- **T3** — subset-sum over open invoices for bundled credits (bounded: ≤6 invoices, ≤200 candidates,
  else escalate to exception); split-payment reassembly via `payment_sequential` semantics.
- **T4** — parent-company payer resolution, unexplained-deduction tolerance bands, duplicate
  detection. Expect to lose most of these. **Report the loss.**

Ambiguity rule: if two allocations are equally plausible, **do not pick one.** Emit
`UNAPPLIED_CASH` with both candidates attached. A confident wrong allocation is worse than an
honest exception — it silently closes an invoice that was never paid.

### 6.3 Acceptance

- Tiered match rates reported separately, never blended into one headline number.
- T3 subset-sum is bounded and never exceeds its candidate cap.
- Every match carries an `explanation` string a human can check in five seconds.
- Property test: `Σ matched + Σ exceptions == Σ input records`, always.

---

## 7. Stage 2 — Exception classifier

`inai/classify.py`. Decision tree over `(match failure mode, residual sign, settlement state,
ledger state, dispute state)`. Deterministic; LLM only writes the human-readable one-liner.

The critical branch — and the one that produces INAI's signature metric:

```
unmatched ledger invoice, status = open, dunning SCHEDULED
  └─ is there ANY bank credit or settlement leg plausibly attributable?
        ├─ yes, high confidence  → UNAPPLIED_CASH
        │                          → auto-apply, CANCEL DUNNING
        │                          → record cost_avoided = false-dunning cost
        ├─ yes, ambiguous        → UNAPPLIED_CASH (unallocated)
        │                          → SUSPEND DUNNING, human queue
        │                          → still counts as false dunning prevented
        └─ no                    → GENUINELY_UNPAID → Stage 3 recovery ladder
```

**Suspension counts.** Even when INAI can't say *which* invoice the money paid, it can say money
arrived — and that alone is enough to stop the chase. Most recon tools treat ambiguity as failure;
here it is a partial win worth rupees.

---

## 8. Stage 3 — Recovery core

Carried over from the recovery design, unchanged in substance.

### 8.1 Diagnosis — `core/diagnose.py`

Two-stage. (1) `config/decline_taxonomy.yaml` maps `(rail, gateway_code) → (RootCause,
Retryability)`, covering ~85%. (2) LLM parses messy narrations into the constrained enum, temp 0;
confidence <0.7 → `UNKNOWN` → exception list. **Never guess to improve coverage.**

`[VERIFY]` every code string against Razorpay's error-code docs and the NPCI return-reason master.
Ship the file as a stub rather than guessing — a wrong code map poisons everything downstream.

| Root cause | Correct intervention | Common mistake |
|---|---|---|
| Insufficient funds | Timed retry on inferred inflow date | Immediate retry, burning a capped slot |
| Issuer down | Hold; resume when bank health recovers | Retry now, then escalate for a bank's fault |
| Mandate revoked / card expired | Re-auth link, **zero** retries | Retry loop at ₹425 each that can never succeed |
| Amount exceeds mandate cap | Split debit or amend mandate | Re-present same amount forever |
| Technical transient | Fast retry in minutes | Escalate to customer |
| Account closed / frozen | Human contact, no retry | Automated dunning into a dead account |

### 8.2 Issuer health — `core/issuer_health.py`

Sliding-window success rate per issuer, seeded from NPCI BD/TD, updated in-run. Retries against a
degraded issuer are **suppressed, not failed** — no retry slot consumed, no strike against the
account. Demo beat: baseline burns three retries into a bank outage; INAI waits.

### 8.3 Inflow timing — `core/inflow.py`

Circular statistics over the payer's own successful-debit history:

```
θ_i = 2π · day_of_month(d_i) / 30
R   = (1/k) Σ (cos θ_i, sin θ_i)
φ   = atan2(R_y, R_x)     → characteristic pay day
κ   = |R|                 → concentration (1 = crisp salary, 0 = diffuse gig income)
retry_day  = round(30φ/2π) + lag
confidence = κ
```

Fall back to population prior when `k < 4` or `κ < 0.3`. Correct *because* pay cycles are periodic —
not a neural net, and better for it.

### 8.4 Uplift scorer — `core/score.py`

The question is not "will this recover?" but "does this action **change** whether it recovers?"

```
τ(a|x)  = P(recover | x, do(a)) − P(recover | x, do(nothing))
EV(a|x) = τ(a|x)·amount_due − cost(a) − annoyance(a,x)
```

`annoyance` = contacts already made this cycle × channel intrusiveness × tenure sensitivity. It is
what stops the agent spamming its way to a flattering gross number.

T-learner over simulated cohorts, or a hand-specified logistic if time is short. **State which.**
A motivated logistic with an honest CI beats an unexplained GBM in a five-minute pitch.

`EV ≤ 0` for every candidate → `NO_ACTION` or `WRITE_OFF`, logged with reason. A deliberate
no-action is a decision and appears in the audit trail.

### 8.5 Policy gate — `core/policy.py`

Pure function `(Candidate, Account, RunState) → GateVerdict`. Declarative YAML, stable rule IDs.

| ID | Rule | Basis |
|---|---|---|
| `POL-RBI-001` | Pre-debit notification ≥24h before any debit | RBI e-mandate |
| `POL-RBI-002` | Debit above AFA threshold without valid AFA → block, route to re-auth | RBI |
| `POL-RBI-003` | Opt-out honoured immediately and permanently | RBI |
| `POL-RBI-004` | Category exemption: FASTag/NCMC auto-replenishment exempt from pre-debit notice | RBI |
| `POL-NPCI-001` | Retries per mandate per cycle ≤ cap | NPCI |
| `POL-NPCI-002` | Execution-rate throttle per rail | NPCI |
| `POL-TRAI-001` | SMS only via DLT-registered template ID | TRAI |
| `POL-TRAI-002` | DND payer → transactional channels only | TRAI |
| `POL-CON-001` | Voice only 09:00–18:00 payer-local | conservative |
| `POL-CON-002` | ≤ N contacts per payer per 7 days, all channels | self-imposed |
| `POL-PTP-001` | Active promise-to-pay → suppress contact until PTP date + grace | self-imposed |
| `POL-DIS-001` | Disputed / hardship / chargeback-in-flight → freeze, human only | self-imposed |
| `POL-CAUSE-001` | `retryability == NO_RETRY` → block all retry actions | derived, §8.1 |
| `POL-RECON-001` | **Unmatched-but-money-arrived → block all dunning** | derived, §7 |

`POL-RECON-001` is the rule that only exists because Stage 1 exists. Point at it in the demo.

**Blocked actions are logged, never silently dropped.** Each verdict carries `rule_id`, `rule_text`
and a `remediation` string. The scorecard reports blocks by rule. Showing *"we wanted to call this
payer and here is the rule that stopped us"* demonstrates bounded autonomy far better than never
proposing the call.

### 8.6 Ladder & PTP

```
silent_retry → upi_collect → whatsapp/sms + link → email → voice → human → write_off
```

Ordering is a prior; EV decides. A ₹200 account never reaches voice; a ₹40,000 premium may skip
straight to it.

PTP state machine:

```
NONE ──capture──▶ ACTIVE ──paid──▶ KEPT      (trust +1, contact cap loosens)
                    ├─ T-24h ▶ one reminder  (the ONLY contact permitted while ACTIVE)
                    └─ date+grace unpaid ──▶ BROKEN (escalate one rung, cap tightens, trust −1)
```

Dates extracted from transcripts by LLM, surfaced for confirmation, never acted on blind.

### 8.7 Where the LLM is allowed

| Allowed | Forbidden |
|---|---|
| Parse messy bank narrations → constrained enum | Any match/no-match decision |
| Extract UTR when regex fails | Retry timing |
| Fill slots in DLT-approved templates, payer language | Free-form outbound messages |
| Hinglish voice conversation + PTP extraction | Any policy-gate verdict |
| Write the human one-liner on each exception | Any recovery probability or EV |
| Summarise a run for audit export | Anything on a determinism-critical path |

State this boundary in the README and the deck. "LLM everywhere" reads as immature; a drawn line
reads as engineering judgement.

### 8.8 P1 — MSME receivables adapter

`adapters/receivables.py` + `msme_interest.py`. Same core, statutory ladder:

```
day 0   invoice issued
day 45  appointed day breached (15 if no written agreement) → §16 interest clock starts
day 60  formal notice quoting MSMED §16 with accrued interest shown
day 90  ODR filing prepared (odr.msme.gov.in — mandatory route since 15 Oct 2025, filing free)
```

Interest is **period-wise**, segmented by MPC date — the bank rate moves, so a single flat rate
across the span is wrong. Test against the ₹10L / 3yr / 5.50% ≈ ₹6.35L worked example, and
cross-validate the engine against the independently computed liability column in the UK
late-payment disclosure data (`DATA.md` §4).

Escalation bounded by statute rather than by an invented policy file — which is exactly what
"compliant escalation with stopping rules" asks for.

---

## 9. Measurement harness

`inai/eval/`. The centre of gravity.

### 9.1 Arms

Seeded, stratified by `(amount_decile, rail, exception_class)`:

- **AGENT** 70% — full pipeline
- **CONTROL** 20% — naive baseline: fixed D1/D3/D5 retries + generic SMS blast, **no reconciliation**
- **PURE_HOLDOUT** 10% — no action at all; measures true self-cure

Three arms, not two. The control arm running *without reconciliation* is what makes false-dunning
measurable: it will chase people the agent knows have already paid, and you can count them.

### 9.2 Reconciliation metrics

```
match_rate(tier)      = matched(tier) / eligible(tier)          # NEVER blended
auto_match_rate       = matched(T0..T2) / total                 # comparable to vendor claims
residual_explained_pct= Σ|residual| attributed to a class / Σ|residual|
exception_rate        = exceptions / total                       # target 5–12%
throughput            = records / second, reported with hardware
```

### 9.3 Recovery metrics

```
self_cure_rate              = gross_recovery_rate(PURE_HOLDOUT)
baseline_rate               = gross_recovery_rate(CONTROL)
incremental_vs_baseline_inr = at_risk(AGENT) × (rate(AGENT) − baseline_rate)   ← HEADLINE
lift_pct                    = (rate(AGENT) − baseline_rate) / baseline_rate × 100
cost_per_100_recovered      = total_cost(AGENT) / incremental_vs_baseline × 100
```

### 9.4 The two metrics only INAI can report

```
false_dunning_prevented_n   = |{ accounts CONTROL contacted that INAI matched as already paid }|
false_dunning_prevented_inr = Σ over those of (contact_cost + modelled_churn_risk × ltv)

rails_leakage_recovered_inr = Σ SHORT_SETTLEMENT
                            + Σ MISSING_REFUND_REVERSAL
                            + Σ UNSETTLED_CAPTURE
                            + Σ FEE_TAX_VARIANCE (adverse)

futile_retries_avoided      = retries(CONTROL on NO_RETRY) − retries(AGENT on same)
futile_retry_savings_inr    = futile_retries_avoided × cost.nach_bounce_fee_inr
```

`false_dunning_prevented` is a Track 03 revenue metric produced by a Track 04 capability. A pure
recovery agent can't compute it (doesn't know the money arrived); a pure recon agent can't compute
it (has no dunning queue to cancel). **This is the proof that the two tracks are one loop.**

`rails_leakage_recovered` is revenue recovery that is literally invisible without reconciliation.

### 9.5 Uncertainty — do not skip

- 95% CI on the rate difference (two-proportion z-interval).
- Bootstrap CI on the rupee figure: 10,000 account-level resamples.
- **If an interval crosses zero, say so on the slide.**
- State the MDE: at n=5,000 with 70/20/10 and ~40% baseline, roughly 4–5pp at 80% power.

A modest lift with a tight interval, plus an admission of where it isn't significant, beats a 70%
claim with no error bars. That *is* the "verification capacity is the bottleneck" thesis, applied
to your own work.

### 9.6 Exception list

Displayed by default, never behind a toggle. Grouped by class, each with machine reason and LLM
one-liner. Target 5–12% of the batch. A submission reporting zero exceptions is either lying or
not trying, and this track's judges will read it that way.

### 9.7 Acceptance

`inai eval --run-id X` emits `scorecard.json`, `match_rates_by_tier.csv`, `exceptions.csv`,
`audit.jsonl`. Seed and config hash printed on the scorecard's face.

---

## 10. Repo layout

```
inai/
  config/
    constants.yaml            # §3, every entry sourced
    decline_taxonomy.yaml     # §8.1  [VERIFY — ship as stub, don't guess]
    policy_rules.yaml         # §8.5
    match_tolerances.yaml     # §6
    channels.yaml             # costs, intrusiveness, DLT template IDs
  configs/  demo.yaml  stress.yaml  smoke.yaml  adversarial.yaml
  data/
    reference/                # NPCI CSVs, fee tables — see DATA.md
    spine/                    # Olist / Online Retail II — see DATA.md
    receivables/              # UK late-payment disclosures — see DATA.md
    fixtures/                 # golden hand-checked cases
  inai/
    schema.py
    sim/        generate.py  corrupt.py  truth.py  narration.py  environment.py
    match/      utr.py  cascade.py  fuzzy.py  subsetsum.py  settlement_math.py
    classify.py
    core/       diagnose.py  inflow.py  issuer_health.py  score.py
                policy.py  ladder.py  ptp.py  orchestrate.py
    baseline/   naive.py
    channels/   base.py simulated.py razorpay.py whatsapp.py sms.py voice.py
    adapters/   receivables.py  msme_interest.py
    llm/        client.py narration.py templates.py transcript.py explain.py
    eval/       arms.py metrics.py bootstrap.py exceptions.py report.py
    store/      duckdb_store.py migrations/
    api/        main.py routes/
    cli.py
  ui/           src/
  tests/
    test_settlement_math.py       # gross→net tie-out, paise-exact
    test_match_conservation.py    # matched + exceptions == input, always
    test_subsetsum_bounded.py     # never exceeds candidate cap
    test_inflow_circular.py       # known φ recovered
    test_policy_gate.py           # one test per POL-* rule
    test_msme_interest.py         # ₹10L / 3yr / 5.50% ≈ ₹6.35L
    test_determinism.py           # same seed → identical scorecard hash
    test_no_truth_leak.py         # core/**, match/** must not import sim.truth
  docs/  DATA.md  SOURCES.md  METHODOLOGY.md
  README.md
```

---

## 11. Build phases

| # | Phase | Hrs | Acceptance |
|---|---|---|---|
| 0 | Skeleton — schemas, DuckDB, CLI, config, CI | 2 | `inai --help`; empty run persists a `run_id` |
| 1 | **Data pipeline** (`DATA.md`) — spine load, forward generation, corruption operators | 7 | 5,000 records, seeded-identical, truth-leak test passes |
| 2 | Settlement math + T0/T1 matcher | 5 | Paise-exact tie-out; conservation test passes |
| 3 | T2/T3/T4 cascade + exception classifier | 6 | Tiered match rates reported; every exception classified |
| 4 | Recovery core — diagnose, inflow, health, scorer | 6 | Retry lands after `funds_available_from` ≥70% vs baseline chance rate |
| 5 | Policy gate + ladder + PTP | 5 | One test per rule; every block carries ID + remediation |
| 6 | **Measurement harness** | 5 | Full scorecard, tiered rates, CIs, exceptions 5–15% |
| 7 | Scorecard UI + audit replay | 6 | Judge clicks any record → full chain, no code walkthrough |
| 8 | Live channel + Hinglish voice on ~20 accounts | 4 | One real end-to-end recovery, recorded |
| 9 | P1 receivables adapter + interest engine | 5 | Interest test passes; second batch through same core |
| 10 | Deck + `METHODOLOGY.md` | 4 | |

Cut order under pressure: **9 → 8 → 7 polish.** Never cut phase 6. Phase 1 is the foundation —
underinvesting there ruins every number downstream.

---

## 12. Demo script — 5 minutes

1. **(30s) The contradiction.** Five vendor recovery benchmarks that can't all be true. "None has a
   control group. Ours does."
2. **(45s) Baseline live.** Naive engine, 5,000 records, no reconciliation. Big flattering gross
   number. Leave it on screen.
3. **(30s) Pure holdout.** Reveal self-cure. Most of that number was never earned.
4. **(45s) Stage 1.** Match rates **by tier**. Show T0 at ~100% and say it proves nothing. Show T2
   and T4. Show the residual attributed in rupees.
5. **(60s) The bridge.** "Of the accounts the baseline chased, **N had already paid.**" Show
   `false_dunning_prevented` in rupees. Show `POL-RECON-001` firing.
6. **(60s) Three audit drill-downs.**
   - Recovered by retry timing alone — zero contacts, zero rupees. Show inferred φ.
   - `MANDATE_REVOKED`: baseline burns three retries at ₹425; INAI refuses all three, sends re-auth.
   - Voice proposed at 21:40, blocked by `POL-CON-001`, rescheduled — show the gate verdict.
7. **(30s) Exceptions.** "412 records we could not resolve, and why."
8. **(15s) Close.** Seed + config hash on screen: "re-run it yourself."

Rehearse until it's under five. Step 5 is the moment the submission wins or loses — do not rush it.

---

## 13. Honest limitations — put these in the deck

State them before a judge finds them.

1. **No public three-way recon dataset exists.** Ours is generated forward from known truth, then
   corrupted with documented failure modes (`DATA.md` §5). What transfers is the method, not the
   absolute match rate.
2. **Bank narration realism is the weakest link.** Grammar derived from published NEFT/UPI formats;
   read T2 results as directional.
3. **Transaction spine is Brazilian (Olist).** Structure transfers — order→multi-payment
   cardinality, installments, timing. Amounts and rails are re-mapped to India.
4. **Recovery propensities are modelled.** Absolute lift is a property of our simulator; the
   three-arm design and exception discipline are what generalise.
5. **Annoyance/churn cost is a proxy**, not measured. Weakest parameter in the EV function.
6. **Regulatory constants move.** Every `[VERIFY]` is a live check, not a one-time lookup.
7. **The uplift model needs real holdout history** to train properly — which most merchants don't
   keep. That's itself a finding worth stating.

---

## 14. One-paragraph pitch

> Every failed-payment recovery vendor publishes a gross recovery rate and none publishes a control
> group, which is why their numbers span 20% to 80% for the same operation. Every reconciliation
> vendor publishes a blended match rate, which is dominated by exact-reference matches that were
> never hard. INAI joins the two, because they are the same loop: it reconciles a batch three ways —
> Razorpay settlement report, bank credits, merchant ledger — ties gross to net through MDR, GST on
> MDR and refund adjustments, reports match rate **by difficulty tier**, then routes every exception
> to a bounded action. Some are chased through a policy gate built on RBI e-mandate rules, NPCI
> retry caps and TRAI messaging law, where each blocked action is logged with the rule that blocked
> it. Others are the opposite of chased: money that already arrived, where the correct action is to
> **cancel the dunning**. INAI reports incremental rupees recovered against both a naive baseline and
> a pure holdout with a 95% confidence interval, rupees clawed back from the rails that nobody had
> noticed, the rupee cost of the false dunning it prevented, and an honest list of every record it
> could not resolve. Seed and config hash are printed on the scorecard. Re-run it yourself.
