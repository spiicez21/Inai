# INAI · DATA.md

**Where the data comes from, how it's generated, and why a Razorpay engineer can't dismiss it.**

Companion to `INAI_SPEC.md`. Read this before writing anything in `inai/sim/` or `inai/match/`.

---

## 0. The honest starting position

**No public dataset exists for three-way settlement reconciliation.** Settlement files, bank
statements and merchant ledgers are the three most confidential artifacts a business owns, and
nobody has published all three joined. Every commercial recon vendor trains on customer data under
NDA.

So the question is not "where is the dataset." It is **"how do I build one whose ground truth is
correct by construction and whose realism is externally anchored."**

Four layers:

| Layer | What's real | What's synthetic |
|---|---|---|
| 1 · Schema | Razorpay's actual settlement report fields, real IDs, real UTRs | — |
| 2 · Spine | Order→payment cardinality, installments, timing, cancellations (Olist / Online Retail II) | Amounts re-scaled to INR, rails re-mapped |
| 3 · Receivables | Invoice-level date/due/paid/days-late/interest (UK public disclosures) | — |
| 4 · Aggregates | NPCI decline rates, downtime, fee tables, bounce fees, AR benchmarks | — |
| 5 · Joins | — | **All of it** — generated forward from truth, then corrupted |

Layer 5 is the only fully synthetic part, and §5 explains why that is a strength rather than an
apology.

---

## 1. Layer 1 — Real schema, from Razorpay

You don't need Razorpay's data. You need Razorpay's *shape*, and that is public.

### 1.1 Settlement report schema

Documented in Razorpay's own SDK repos (`razorpay-node`, `razorpay-php`, `razorpay-java`,
`documents/settlement.md`). Fields, verbatim:

```
entity_id       pay_… / rfnd_… / adj_… / disp_…
type            payment | refund | adjustment | dispute | transfer
debit           paise
credit          paise
amount          paise
currency        INR
fee             paise   ← MDR
tax             paise   ← GST on MDR
on_hold         bool
settled         bool
created_at      unix
settled_at      unix
settlement_id   setl_…
posted_at       unix | null
credit_type     default | …
description     free text
notes           json
payment_id      pay_… | null
settlement_utr  ← THE JOIN KEY into the bank statement
order_id        order_…
order_receipt   merchant's own reference | null
method          card | upi | netbanking | wallet | emandate
card_network    | card_issuer | card_type
dispute_id      disp_… | null
```

Generate your synthetic settlement file to **exactly** this schema, paise as integers. Using
`settlement_utr` as the reconciliation join key is not a detail — it's the single fact that shows
you read their docs rather than invented a CSV.

### 1.2 Razorpay test mode — do this on day one

You can generate a **genuinely real settlement report** at zero cost:

```
1. Create a Razorpay test-mode account; get test API keys.
2. Create orders + payments across methods (card / upi / netbanking / wallet).
3. Capture some, refund some fully, refund some partially, leave some authorised-not-captured.
4. Let settlements form (or use the settlements API in test mode).
5. Pull:  instance.settlements.reports({ year, month })
6. Persist to data/reference/razorpay_settlement_sample.json
```

Use it for three things:
- **Schema conformance test** — assert your generator's output validates against the real payload shape.
- **UTR format** — derive the real UTR grammar for §4 narration generation instead of inventing one.
- **Credibility** — one slide showing a real test-mode settlement report next to your generated one.

`[VERIFY]` Razorpay reports API constraints — a 95-day window applies to most report types, with
current/previous financial year available for Payments, Settlements and Settlement Reconciliation.

### 1.3 The problem statement, in Razorpay's own terms

> A settlement lands as a single lumped NEFT credit covering hundreds of orders, net of MDR, 18% GST
> on MDR, and refund deductions. Reconciliation means unpacking that net figure **order by order**,
> not matching the lump sum.

That is `settlement_math.py` (`INAI_SPEC.md` §6.1) in one sentence.

---

## 2. Layer 2 — Real transaction spine

Real order/payment behaviour for structure; localised for India.

### 2.1 Primary: Olist Brazilian E-Commerce (Kaggle)

~99,441 orders, Sep 2016 – Oct 2018, 8 CSVs, anonymised, public licence.

The table that matters is `olist_order_payments_dataset`:

| Column | Why it matters here |
|---|---|
| `order_id` | ledger join |
| **`payment_sequential`** | **a customer may pay one order with multiple payment methods** — real many-to-one behaviour that breaks naive matchers |
| `payment_type` | credit_card / boleto / voucher / debit_card → remap to Indian rails |
| **`payment_installments`** | real split-payment structure for the T3 tier |
| `payment_value` | amount distribution shape |

Also use: `olist_orders_dataset` (status incl. cancelled/unavailable, purchase→approval→delivery
timestamps for realistic lag), `olist_customers_dataset` (customer identity, repeat behaviour).

**Localisation mapping** (`sim/localize.py`):

```python
RAIL_MAP = {
    "credit_card": weighted(["card_mandate", "card"]),
    "debit_card":  "card",
    "boleto":      "netbanking",      # bank-transfer analogue
    "voucher":     "wallet",
}
# Amounts: rank-preserving rescale of payment_value onto an INR lognormal
#          fitted to the merchant profile in configs/*.yaml.
# Method mix: re-weight toward Indian reality (UPI-dominant), NOT Brazil's
#             credit-card dominance. Document the re-weighting in the deck.
```

**Say in the deck: only the structure transfers, not the amounts.** That single sentence costs
nothing and protects the whole methodology from a fair objection.

### 2.2 Alternative spine: UCI Online Retail II

~1M rows, real invoice numbers, real customer IDs, and — usefully — **cancellations encoded as
negative quantities with a `C`-prefixed invoice number**. Cancellations are a genuine recon edge
case (invoice cancelled after payment captured). Use this spine if you want invoice-level rather
than order-level granularity.

---

## 3. Layer 3 — Real receivables data with ground-truth payment timing

The best find for the B2B half, and almost nobody knows it exists.

UK public bodies are legally required to publish **invoice-level late-payment disclosures**. The
files carry exactly the columns an AR engine needs:

```
Supplier Name | Invoice Date | Due Date | Date Paid | Number of Days Late
              | Gross Amount of Invoice | Liability calculated
```

Real examples with thousands of rows: Dover District Council FOI disclosure log
(`FI16021 Late Payment Data`, parts 1–4), and central-government prompt-payment datasets on
data.gov.uk (e.g. DWP quarterly: % paid within 5 days, % within 30 days, late-payment interest).

**Three uses:**

1. **Fit realistic days-late distributions** for the receivables simulator instead of inventing them.
   The observed tail is long — some rows sit at 299, 384, even 840 days late.
2. **Validate the interest engine.** The `Liability calculated` column is an independently computed
   statutory interest figure. Your `msme_interest.py` uses a different rate basis (MSMED §16, 3×
   RBI bank rate, monthly rests) — but the *compounding mechanics* are checkable: swap in the UK
   rate basis, recompute, and assert you reproduce their column. That's a free correctness proof on
   the hardest arithmetic in the build.
3. **Realistic payer archetypes** — the data shows the same suppliers paid late repeatedly, which is
   the behavioural pattern the recovery scorer keys on.

India-side aggregates (pitch, not row-level): MSME Samadhaan — 256,892 applications worth
₹55,244 cr filed as of 14 Aug 2026, ₹20,979 cr pending, 40,580 (16%) unresolved beyond a year.

---

## 4. Layer 4 — Real aggregates for calibration

Pull to `data/reference/` at build time. **Never scrape at runtime.**

| Source | URL | Feeds |
|---|---|---|
| NPCI Declined (BD/TD) & Uptime | `npci.org.in/statistics/bd-td-and-uptime` | per-bank decline priors → `issuer_health.py` |
| NPCI Retail Payment Statistics | `npci.org.in/retail-payment-statistics` | NACH presentations/returns → bounce seasonality |
| NPCI UPI Ecosystem Statistics | `npci.org.in/what-we-do/upi/upi-ecosystem-statistics` | canonical BD/TD definitions — copy verbatim into the taxonomy |
| Bank-wise UPI PSP performance 2022– | `dataful.in/datasets/18242/` | pre-compiled BD/TD time series |
| NPCI unscheduled downtime & incidents | `dataful.in/datasets/415/` | realistic outage clustering |
| MSME Samadhaan | `samadhaan.msme.gov.in` | P1 claim volumes, state/buyer mix |
| UK late-payment disclosures | data.gov.uk / council FOI logs | §3 |
| Razorpay settlement docs | `github.com/razorpay/razorpay-node` `documents/settlement.md` | §1.1 |

`[VERIFY]` Pull the **current month** NACH presentations/returns before demo. Do not present 2021
figures as current.

### 4.1 Bank narration grammar — the weakest link, named

There is no public corpus of Indian bank statement narrations. Build a grammar instead:

```
NEFT:  "NEFT-{UTR}-{REMITTER_NAME}-{REF}"
IMPS:  "IMPS/{RRN}/{REMITTER}/{REMARK}"
UPI:   "UPI/{RRN}/{VPA}/{NOTE}"
RTGS:  "RTGS-{UTR}-{REMITTER}"
```

Take the **real UTR format** from your test-mode settlements (§1.2). Then apply the narration
corruption operators in §5.

**State the limitation on a slide:** *"Narration realism is our largest synthetic-data risk. The
grammar derives from published transfer formats and real Razorpay UTRs; the T2 fuzzy-match tier
should be read as directional."* That sentence inoculates the entire methodology and costs you
nothing.

---

## 5. The method: generate forward, then corrupt

This is what removes the "your data is fake" objection. **You never hand-label anything.**

```
STEP 1  Generate ledger truth from the spine:
          invoice → order → payment(s) → settlement leg(s) → bank credit
        Every link known by construction. The match answer is free AND provably correct.

STEP 2  Compute the real money chain:
          gross − MDR − GST(MDR) − TCS ± refunds ± disputes + adjustments = net credit
        Paise-exact. This is the arithmetic the matcher must later rediscover.

STEP 3  Apply CORRUPTION OPERATORS — each one a documented real-world failure mode.
        Record which operators fired on which record → that determines its difficulty tier.

STEP 4  Hand the corrupted artifacts to the matcher. Score against STEP 1.
```

Because truth precedes corruption, ground truth is **correct by construction**. No labelling, no
annotator disagreement, no "we eyeballed 200 rows."

### 5.1 Corruption operators

`inai/sim/corrupt.py`. Uniform interface:

```python
class CorruptionOperator(Protocol):
    id: str
    tier_contribution: MatchTier
    def applies_to(self, record: LedgerChain, rng: Generator) -> bool: ...
    def apply(self, record: LedgerChain, rng: Generator) -> LedgerChain: ...
```

| ID | Operator | Documented real cause | Produces | Tier |
|---|---|---|---|---|
| `C01` | Strip remittance reference | Payment message arrives with no invoice reference | `UNAPPLIED_CASH` | T2 |
| `C02` | Bundle N invoices into one credit | Customer has several open invoices totalling the payment amount | Ambiguous allocation | T3 |
| `C03` | Split one invoice across payments | Olist `payment_sequential` — real behaviour | `PARTIAL_PAYMENT` | T3 |
| `C04` | Shift settlement T+1…T+7 | Variable settlement cycle by gateway/tier | `TIMING_DIFFERENCE` | T1 |
| `C05` | Perturb fee ±δ | MDR rounding, tier changes, method mix | `FEE_TAX_VARIANCE` | T1 |
| `C06` | Drop a refund reversal | Refund debited, never credited back | `MISSING_REFUND_REVERSAL` | T1 |
| `C07` | Mangle / truncate narration | Bank field limits, OCR, abbreviation | fuzzy match required | T2 |
| `C08` | Pay from parent-company account | Customers pay with their parent company's bank account | Wrong-payer identity | T4 |
| `C09` | Duplicate a credit | Double submission | `DUPLICATE_PAYMENT` | T4 |
| `C10` | Unexplained deduction | Customers deduct amounts you've never heard of | `SHORT_SETTLEMENT` | T4 |
| `C11` | Capture without settlement | Payment captured, settlement never formed | `UNSETTLED_CAPTURE` | T1 |
| `C12` | Chargeback mid-flight | Dispute raised, funds withheld | `DISPUTE_HOLD` | T1 |
| `C13` | Cancel invoice post-capture | Online Retail II `C`-prefixed cancellations | Negative reconciliation | T3 |
| `C14` | Mixed-language / casing narration | Real Indian bank statements | fuzzy match required | T2 |

Configure application rates in `configs/*.yaml`. `adversarial.yaml` raises C08–C10 sharply — that's
your named "hard set."

### 5.2 Difficulty tiers

A record's tier = the **hardest** tier among the operators that fired on it. Report match rate per
tier, never blended:

| Tier | Definition | Target | What it proves |
|---|---|---|---|
| **T0** exact | Unique UTR or `order_id` both ways | ~100% | **Nothing. Say so on the slide.** |
| **T1** deterministic | Amount + date + payer within tolerance | > 97% | Baseline competence |
| **T2** fuzzy | Mangled narration, name similarity + amount constraint | 80–90% | **The real score** |
| **T3** structural | Bundled, split, partial, cancelled | 60–75% | Genuine engineering |
| **T4** adversarial | Parent-co payer, unexplained deduction, duplicate | **< 50% expected** | Intellectual honesty |

Vendors claim 95%+ automated matching. Reporting **91% overall with the tier breakdown and an
exception list** is a stronger submission than claiming 97% flat — and it's the direct answer to
Track 04's own bar: *"one cherry-picked match proves nothing."*

**Voluntarily reporting your worst tier is the single most credible move available to you.**

### 5.3 Ground-truth contract

```
inai/sim/truth.py   — the ONLY module that knows the answer.
                      Writes ground_truth to a SEPARATE DuckDB schema.

FORBIDDEN: inai/core/**, inai/match/**, inai/classify.py importing inai.sim.truth
ENFORCED:  tests/test_no_truth_leak.py — AST scan of imports, runs in CI
```

Latent recovery states (hidden, for the recovery half — see `INAI_SPEC.md` §8.4):

| State | Share | Behaviour |
|---|---|---|
| `self_curing` | ~35% | Recovers in 14 days with or without intervention. Contacting them costs money and buys nothing. **This is the population that inflates every vendor benchmark.** |
| `persuadable` | ~20% | Recovers only if contacted on a responsive channel in their window. The only population where outreach creates value. |
| `retry_only` | ~15% | Recovers on a correctly-timed retry; outreach is irrelevant and mildly annoying. |
| `unreachable` | ~15% | Hard decline. No retry ever works. Needs re-auth or amendment. |
| `hopeless` | ~15% | Won't recover this cycle by any means. Correct action is early write-off. |

Since you own the labels, compute the **oracle gap** for free: incremental recovery achieved ÷
incremental recovery a perfect policy would achieve. Rare in hackathon submissions, costs nothing.

---

## 6. Scale and batch design

Track 04 asks for 50+ records. **Run 5,000+, tiered.**

```
configs/smoke.yaml        n=200      CI, fast iteration
configs/demo.yaml         n=5,000    the headline run
configs/stress.yaml       n=25,000   throughput claim (records/sec, hardware stated)
configs/adversarial.yaml  n=1,000    C08–C10 heavy — the named hard set
```

Report throughput with hardware. Field observation says teams burn 15–25 hours/month at 800–1,000
entries; if INAI clears 5,000 in seconds, that comparison is your throughput slide.

---

## 7. Constants → source map

Every number in `config/constants.yaml` carries `source` and `as_of`. Summary:

| Constant group | Anchored to |
|---|---|
| MDR by method (0% UPI, 1.5–2% debit, 2.5–3.5% intl credit), 18% GST on MDR, TCS, T+1…T+7 | practitioner settlement reference |
| Unapplied cash ≤ 2–3% of AR | AR practice benchmark |
| 23% automation rate, 30% manual DSO penalty, 52% cite manual process | Blackline B2B AR benchmarking |
| 800–1,000 txn threshold, 15–25 hrs/month, 1,000 txn close-delay threshold | field observation |
| 95%+ vendor match-rate claim | vendor marketing — the bar, not the truth |
| TD <1%, BD <5%, TD 8–10% (2016) → ~0.8% (2025) | NPCI Circular OC-149 (Jun 2022) |
| NACH bounce 31.5%/24.9% (Feb 2020), 31.24%/24.83% (Oct 2021), 45.4% peak (Jun 2020) | NPCI |
| Recurring debit failure 10–15%; card ~15% vs ACH/DD 3–5% | Indian merchant reporting / industry |
| NACH bounce fee ₹350–500 | originating-bank charge |
| RBI 24h pre-debit, AFA ₹15,000 / ₹1,00,000, opt-out, FASTag/NCMC exemption | RBI e-mandate framework `[VERIFY]` |
| MSMED §16: 3× bank rate, monthly rests; 5.50% → 16.50% / ≈17.81%; ₹10L·3yr ≈ ₹6.35L | MSMED Act + RBI MPC Aug 2026 `[VERIFY]` |
| Involuntary churn 20–40% / 40–50%; open rate 41.3% vs 26.8%; +25% retry-timing lift | industry benchmarks — **pitch only, never simulator truth** |

---

## 8. Test data strategy

Three separate things, don't conflate them:

**Golden fixtures** (`data/fixtures/`) — ~30 hand-constructed cases with hand-checked answers, one
per corruption operator plus the nastiest combinations. Run in CI on every commit. These catch
regressions the statistical tests miss.

**Property tests** — invariants that must hold on every run:
- `Σ matched + Σ exceptions == Σ input records` (conservation)
- `Σ settlement legs − fees − taxes == bank credit` on uncorrupted records (paise-exact)
- Subset-sum candidate count never exceeds its cap
- Same seed → identical scorecard hash
- No module under `core/` or `match/` imports `sim.truth`

**Evaluation runs** — the four configs in §6. Only these produce reportable numbers.

---

## 9. Day-one checklist

```
[ ] Razorpay test-mode account created, test keys in .env (never committed)
[ ] settlements.reports() pulled → data/reference/razorpay_settlement_sample.json
[ ] Real settlement schema encoded in schema.py, paise as int, validated against the sample
[ ] Olist CSVs → data/spine/
[ ] UK late-payment disclosure files → data/receivables/
[ ] NPCI BD/TD + downtime CSVs → data/reference/
[ ] config/constants.yaml populated from §7, every entry with source + as_of + verify
[ ] tests/test_no_truth_leak.py wired into CI BEFORE writing sim/truth.py
[ ] configs/smoke.yaml runs end-to-end with a stub matcher
```

---

## 10. What to say when a judge asks "is this real data?"

> "The schema is real — pulled from Razorpay's own settlement report in test mode. The transaction
> structure is real — Olist, ninety-nine thousand orders with genuine multi-payment and installment
> behaviour. The receivables timing is real — UK statutory late-payment disclosures, invoice-level,
> with independently computed interest we validate our engine against. The failure rates, fee
> tables and downtime windows are real NPCI and published figures.
>
> The **joins** are synthetic, because no public dataset joins settlement files to bank statements
> to ledgers — those are the three most confidential artifacts a business owns. So we generate the
> chain forward from known truth and then corrupt it with fourteen documented failure modes. That
> makes our ground truth correct by construction rather than hand-labelled, and it lets us report
> match rate by difficulty tier instead of one blended number that's dominated by matches that were
> never hard.
>
> The weakest link is bank narration realism, and it's on slide fourteen."
