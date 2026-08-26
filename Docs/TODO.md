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
| 1 · Data pipeline | Not started |
| 2 · Settlement math + T0/T1 | Not started |
| 3 · T2/T3/T4 + classifier | Not started |
| 4 · Recovery core | Not started |
| 5 · Policy gate + ladder + PTP | Not started |
| 6 · Measurement harness | Contracts only — `Scorecard` shape is fixed, values are fabricated |
| 7 · Scorecard UI | **Shell done** — reads real artifacts, drill-down works; decision chain pending phases 4–5 |
| 8 · Live channel + voice | Not started |
| 9 · P1 receivables | Not started |
| 10 · Deck + METHODOLOGY | Not started |

`inai run` currently emits a **placeholder scorecard**: correct shape, fabricated numbers,
banner-flagged on both the CLI and the dashboard. Delete `_placeholder_*` in
`inai/pipeline.py` as the real stages land.

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

## Phase 1 · Data pipeline — 7h — NEXT

The foundation. Everything downstream inherits its quality. `DATA.md` §5.

### Day-one checklist (`DATA.md` §9)
- [ ] Razorpay test-mode account; test keys in `.env` (never committed)
- [ ] `settlements.reports()` → `data/reference/razorpay_settlement_sample.json`
- [ ] Assert generator output validates against that real payload shape
- [ ] Derive the real UTR grammar from it — do not invent one
- [ ] Olist CSVs → `data/spine/`
- [ ] UK late-payment disclosures → `data/receivables/`
- [ ] NPCI BD/TD + downtime CSVs → `data/reference/`

### Build
- [ ] `sim/localize.py` — `RAIL_MAP`, rank-preserving INR rescale, UPI-dominant re-weighting
- [ ] `sim/generate.py` — forward chain: invoice → order → payment(s) → leg(s) → bank credit
- [ ] `sim/narration.py` — NEFT/IMPS/UPI/RTGS grammar
- [ ] `sim/corrupt.py` — all 14 operators C01–C14, each recording which fired
- [ ] `sim/truth.py` — write `TruthLink` rows; tier = hardest operator that fired
- [ ] Child RNG stream per operator (`rng.spawn`), so reordering operators cannot change output

**Acceptance:** 5,000 records, seeded-identical across runs, truth-leak test passes.

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
