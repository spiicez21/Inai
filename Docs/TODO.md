# INAI · TODO

Build order and acceptance criteria from `INAI_SPEC.md` §11. Data-layer detail in `DATA.md`.

**Cut order under pressure: 9 → 8 → 7 polish. Never cut phase 6.**
Phase 1 is the foundation — underinvesting there ruins every number downstream.

Status as of 2026-08-26.

---

## Where we actually are

| Phase | State |
|---|---|
| 0 · Skeleton | **Done** — schemas, config, store, CLI, CI, truth-leak guard, 88 tests green |
| 1 · Data pipeline | **Done** — Olist spine, forward generation, 14 operators, 5,000 records at ~3,000 rec/s |
| 2 · Settlement math + T0/T1 | **NEXT** |
| 3 · T2/T3/T4 + classifier | Not started |
| 4 · Recovery core | Not started |
| 5 · Policy gate + ladder + PTP | Not started |
| 6 · Measurement harness | Contracts only — `Scorecard` shape is fixed, values are fabricated |
| 7 · Scorecard UI | **Shell done** — reads real artifacts, drill-down works; decision chain pending phases 4–5 |
| 8 · Live channel + voice | Not started |
| 9 · P1 receivables | Not started |
| 10 · Deck + METHODOLOGY | Not started |

`inai run` now emits a **partial scorecard**: the records, amounts, settlements and difficulty
tiers are REAL (phase 1); the match rates, recovery figures and bridge metrics are still
fabricated. Flagged by `Scorecard.provenance_warning` on the CLI and the dashboard. Delete
`_placeholder_*` in `inai/pipeline.py` as phases 2-6 land.

---

## Phase 0 · Skeleton — DONE

- [x] `inai/schema.py` — all of §5 as frozen Pydantic
- [x] `inai/money.py` — `Paise` int everywhere; rupees only at the IO boundary
- [x] `config/constants.yaml` — every entry carries `value/unit/source/as_of/verify`
- [x] `configs/` — smoke · demo · stress · adversarial
- [x] DuckDB store, `ground_truth` in a separate schema
- [x] `inai` CLI — `run` · `eval` · `constants` · `verify`
- [x] Truth-leak guard: ruff `TID251` + `tests/test_no_truth_leak.py`
- [x] Determinism test — same seed, same scorecard
- [x] CI workflow written
- [ ] **CI has never executed on a runner.** Push a branch and confirm it goes green.

---

## Phase 1 · Data pipeline — DONE

Olist spine is in `data/spine/` (git-ignored, CC BY-NC-SA).

- [x] `sim/spine.py` — loads Olist, samples **customer-first** so repeat payers exist
- [x] `sim/localize.py` — `RAIL_MAP`, rank-preserving INR rescale, UPI-dominant re-weighting
- [x] `sim/narration.py` — NEFT/IMPS/UPI/RTGS grammar, 16-char UTR
- [x] `sim/generate.py` — forward chain, paise-exact `gross − MDR − GST − TCS ± refunds`
- [x] `sim/corrupt.py` — all 14 operators C01–C14, each recording which fired
- [x] `sim/truth.py` — `TruthLink`, tier = hardest operator that fired, oracle-gap flag
- [x] `sim/build.py` — generate → corrupt → truth
- [x] Child RNG stream per operator, keyed by *sorted* id
- [x] Persisted to DuckDB; truth to the separate `ground_truth` schema
- [x] 21 property tests in `tests/test_generation.py`

**Acceptance met:** 4,999 records from `demo.yaml`, seeded-identical, truth-leak test passes.

Measured at 5,000 records: 56.8 orders per settlement, tiers T0 52.8% / T1 12.2% /
T2 21.9% / T3 8.1% / T4 5.1%, all 14 operators firing, 690 repeat payers.
Throughput ~3,000 rec/s at 5k and ~4,250 rec/s at 25k.

### Four decisions taken during the build, all deck-relevant

1. **Customer-first sampling with a `repeat_boost`.** Olist issues a fresh `customer_id`
   per order; `customer_unique_id` is the real payer. Order-first sampling gave every
   invoice its own customer, so C02 (bundle N invoices into one credit) could never fire
   and the recovery scorer had no repeat-payer history. `repeat_boost` then oversamples
   multi-order customers — a **deliberate deviation** from the spine's distribution,
   because Olist is consumer e-commerce and INAI targets recurring/B2B receivables.
2. **Timeline compression.** The spine spans Sep 2016 – Oct 2018. Keyed by value date that
   produced ~168 settlements of one order each, when the entire problem statement is one
   lumped credit covering hundreds of orders. Compressed to a 90-day operating window,
   rank-preserving, anchored to a fixed date so a run cannot change because the clock did.
3. **Two operator kinds.** DATA.md's per-record `Protocol` cannot express C02 or C09;
   both need several chains at once. `BatchOperator` is the second interface.
4. **Arrow-registered inserts, not `executemany`.** Parameterised executemany took **180
   seconds** for 15,000 rows; registering an Arrow frame takes **1.4 seconds**. Without
   this the throughput slide would have been a lie.

### Still outstanding from the day-one checklist

- [ ] **Razorpay test-mode account** → `data/reference/razorpay_settlement_sample.json`.
      Needed for the schema-conformance test and to replace the *synthetic* UTR grammar
      with the observed one (`narration.utr_grammar_from_sample` currently raises).
      **Bank narration realism remains the largest synthetic-data risk — slide 14.**
- [ ] NPCI BD/TD + downtime CSVs → `data/reference/` (phase 4 needs them)
- [ ] UK late-payment disclosures → `data/receivables/` (phase 9)
- [ ] Golden fixtures, ~30 hand-checked cases → `data/fixtures/` (DATA.md §8)
---


## Phase 2 · Settlement math + T0/T1 — 5h

- [ ] `match/settlement_math.py` — gross→net tie-out, paise-exact
- [ ] `match/utr.py` — regex extraction; LLM only on regex failure
- [ ] `match/cascade.py` — T0 (unique UTR / order_id), T1 (amount ±₹1, date window, payer)
- [ ] `tests/test_settlement_math.py`
- [ ] `tests/test_match_conservation.py` — `Σ matched + Σ exceptions == Σ input`

**Acceptance:** paise-exact tie-out; conservation holds on every run.

---

## Phase 3 · T2/T3/T4 + classifier — 6h

- [ ] `match/fuzzy.py` — RapidFuzz `token_set_ratio`, amount as a hard constraint
- [ ] `match/subsetsum.py` — bounded ≤6 invoices / ≤200 candidates, else escalate
- [ ] T4 — parent-co payer, unexplained-deduction bands, duplicate detection
- [ ] **Ambiguity rule:** two equally plausible allocations → do NOT pick. Emit
      `UNAPPLIED_CASH` with both candidates attached
- [ ] `classify.py` — decision tree, 11 classes, deterministic
- [ ] `tests/test_subsetsum_bounded.py`

**Acceptance:** tiered rates reported separately; every exception classified; every match
carries an explanation a human can check in five seconds.

---

## Phase 4 · Recovery core — 6h

- [ ] `config/decline_taxonomy.yaml` — **ship as a stub rather than guessing.** Every code
      string `[VERIFY]` against Razorpay error docs + the NPCI return-reason master
- [ ] `core/diagnose.py` — taxonomy first, LLM only for the residue; confidence <0.7 → UNKNOWN
- [ ] `core/issuer_health.py` — sliding window; degraded issuer → **suppressed, not failed**
- [ ] `core/inflow.py` — circular stats; fall back to prior when k<4 or κ<0.3
- [ ] `core/score.py` — uplift τ and EV. **State which model was used** (logistic vs T-learner)
- [ ] `tests/test_inflow_circular.py` — known φ recovered

**Acceptance:** retry lands after `funds_available_from` ≥70% vs baseline chance rate.

---

## Phase 5 · Policy gate + ladder + PTP — 5h

- [ ] `config/policy_rules.yaml` — declarative, stable rule IDs
- [ ] `core/policy.py` — pure `(Candidate, Account, RunState) → GateVerdict`
- [ ] All 14 `POL-*` rules from §8.5, each with `rule_text` + `remediation`
- [ ] `core/ladder.py`, `core/ptp.py` — PTP state machine, one reminder at T-24h
- [ ] `tests/test_policy_gate.py` — **one test per rule**

**Acceptance:** every block carries an ID and a remediation; nothing silently dropped.

---

## Phase 6 · Measurement harness — 5h — NEVER CUT

- [ ] `eval/arms.py` — seeded, stratified by `(amount_decile, rail, exception_class)`
- [ ] `baseline/naive.py` — fixed D1/D3/D5 retries + generic SMS, **no reconciliation**
- [ ] `eval/metrics.py` — §9.2 and §9.3 exactly as written
- [ ] `eval/bootstrap.py` — two-proportion z + 10,000-resample bootstrap
- [ ] The two bridge metrics (§9.4) computed for real, not fabricated
- [ ] Oracle gap — free, since we own the labels

**Acceptance:** full scorecard, tiered rates, CIs, exceptions land in 5–15%.

---

## Phase 7 · UI — shell done, rest pending upstream

- [x] Artifacts-first: reads `runs/{run_id}/` over HTTP, no server on the critical path
- [x] DuckDB-Wasm over Parquet — 25,000 rows, virtualised, filtered in SQL
- [x] Light + dark, tokens flip at runtime; charts follow the theme
- [x] Tier distribution strip doubles as the tier filter
- [x] Drill-down drawer, deep-linkable via `?run=…&exc=…`
- [ ] **Decision chain in the drawer** — diagnosis, every scored candidate *including the
      rejected ones*, gate verdict, outcome. Blocked on phases 4–5
- [ ] Audit replay view
- [ ] Run picker (currently only `?run=` or `latest.json`)

**Acceptance:** judge clicks any record → full chain, no code walkthrough.

---

## Phase 8 · Live channel + Hinglish voice — 4h

- [ ] `channels/` — razorpay · whatsapp · sms · voice
- [ ] ~20 real accounts, one recorded end-to-end recovery

---

## Phase 9 · P1 receivables — 5h

- [ ] `adapters/receivables.py`, `adapters/msme_interest.py`
- [ ] Period-wise interest, segmented by MPC date — a flat rate across the span is wrong
- [ ] `tests/test_msme_interest.py` — ₹10L / 3yr / 5.50% ≈ ₹6.35L
- [ ] Cross-validate against the UK `Liability calculated` column (`DATA.md` §3)

---

## Phase 10 · Deck + METHODOLOGY — 4h

- [ ] `docs/METHODOLOGY.md`, `docs/SOURCES.md`
- [ ] Deck, and rehearse §12 until it is **under five minutes**
- [ ] **Limitations (§13) must appear in the deck.** They were removed from the dashboard on
      2026-08-26 — they still ship in `scorecard.json` and print in the CLI, but the deck is
      now the only place a judge will see them. Slide 14 is the narration-realism admission
- [ ] Slide: real test-mode settlement report next to the generated one

---

## Known debt / decisions taken

- **The provenance warning is now a dedicated `Scorecard.provenance_warning` field**, not
  a magic prefix in `limitations`. It was a prefix; renaming the banner text silently
  removed it from the dashboard while the fabricated numbers stayed on screen.
  `tests/test_determinism.py` fails if it is cleared while figures are still synthetic.
- **`temperature` is removed on current Claude models** — `INAI_SPEC.md` §8.1's "temp 0"
  returns a 400. Use `output_config: {format, effort}` + `strict: true` instead.
- **Model pinned to `claude-opus-5`**, not the spec's `claude-sonnet-4-6` (stale). Flagged
  `verify: true` in `constants.yaml`.
- **LLM replay cache is not built yet** and is *mandatory* for §0.5 determinism — an LLM is
  not deterministic at any setting. Content-addressed under `data/llm_cache/`, committed to
  git, `INAI_LLM=replay` a hard error on miss. Build it before the first LLM call ships.
- **Money is int paise everywhere**, including ledger/bank sides that §5.1/§5.3 wrote as
  `Decimal`. Mixed units across three sides is the bug class §5.2 warns about.
- **`TRUTH_SCHEMA` lives in the store**, not in `sim.truth` — the store is shared
  infrastructure, and importing the truth module there put a hole in the ban rule.
- **`@theme static` in `ui/src/index.css` is load-bearing** — Tailwind v4 tree-shakes theme
  variables it cannot see used, and many tokens are only referenced from JS. Without it the
  tier ramp silently resolves to transparent.
- Config files still missing: `match_tolerances.yaml`, `channels.yaml` (tolerances currently
  live inside `constants.yaml` under `match:`).
- Golden fixtures (`data/fixtures/`, ~30 hand-checked cases) not built. `DATA.md` §8.

---

## Standing rules

- `[VERIFY]` is a live check before demo day, not a one-time lookup. Run `inai verify`.
- Pull the **current month** NACH presentations/returns. Never present 2021 figures as current.
- No unseeded RNG. No LLM on a scoring, matching or policy path.
- Report the worst tier voluntarily. It is the most credible move available.
