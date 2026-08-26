# INAI · இணை

**Match first. Then chase.**

*iṇai* (இணை, Tamil) — to match, to pair, to join.
Reconciliation-first revenue recovery.

Razorpay AI Buildathon — one agent, one loop, both tracks.
Track 03 (AI Revenue Recovery) + Track 04 (AI Finance Controller).

---

## The thesis in one line

**Revenue at risk is not only revenue that failed to arrive. It is also revenue that arrived
and was never recognised.** So the reconciliation exception list *is* the revenue-at-risk
queue — one artifact, two tracks.

Read [`Docs/INAI_SPEC.md`](Docs/INAI_SPEC.md) for the executable specification and
[`Docs/DATA.md`](Docs/DATA.md) for where the data comes from. Both before writing code.

---

## Status

**Phase 0 — skeleton.** Schemas, config, store, CLI, CI and the UI shell are in place.
The matcher, classifier and recovery core are not. `inai run` currently emits a scorecard
of the correct *shape* with fabricated numbers, banner-flagged as `PLACEHOLDER RUN` on both
the CLI and the dashboard, so the measurement harness and UI can be built against something
real. See `INAI_SPEC.md` §11 for the phase order and acceptance criteria.

---

## Quickstart

```bash
uv sync
uv run inai run --config configs/smoke.yaml --seed 42
```

```bash
cd ui && bun install && bun run dev
```

The UI reads `runs/{run_id}/` directly. No server on the critical path.

---

## Where the LLM is allowed

`INAI_SPEC.md` §8.7 draws the line, and it is drawn deliberately:

| Allowed | Forbidden |
|---|---|
| Parse messy bank narrations into a constrained enum | Any match / no-match decision |
| Extract a UTR when the regex fails | Retry timing |
| Fill slots in DLT-approved templates | Free-form outbound messages |
| Write the human one-liner on an exception | Any policy-gate verdict |
| Summarise a run for audit export | Any recovery probability or EV |

Every LLM call is content-addressed and replayed from `data/llm_cache/` during evaluation, so
`(seed, config_hash) → identical scorecard` survives contact with a non-deterministic model.
`INAI_LLM=live` is the only mode that may make a network call.

---

## The reproducibility contract

```
(seed, config_hash) -> identical scorecard
```

Enforced by `tests/test_determinism.py`. Seed and config hash are printed on the face of every
scorecard. Re-run it yourself.

## The ground-truth contract

`inai/sim/truth.py` is the only module that knows the answer. Nothing under `inai/match/**`,
`inai/core/**` or `inai/classify.py` may import it — enforced twice, by ruff `TID251` in the
editor and `tests/test_no_truth_leak.py` in CI. Truth precedes corruption, so ground truth is
correct by construction rather than hand-labelled.

---

## Commands

```bash
uv run inai run --config configs/demo.yaml --seed 42   # the headline run
uv run inai eval --run-id <run_id>                     # re-print a scorecard
uv run inai constants cost.nach_bounce_fee_inr         # a number WITH its provenance
uv run inai verify                                     # every [VERIFY] constant due a re-check
```

## Layout

```
config/     constants.yaml — every entry carries value/unit/source/as_of/verify
configs/    smoke · demo · stress · adversarial
inai/
  money.py    Paise(int). The only two places rupees exist are the IO boundaries.
  schema.py   Pydantic contracts; DuckDB tables mirror them 1:1
  sim/        generator + corruption operators + truth (quarantined)
  match/      T0 exact -> T1 deterministic -> T2 fuzzy -> T3 structural -> T4 adversarial
  core/       diagnose · inflow · issuer health · uplift scorer · policy gate · ladder
  eval/       the measurement harness — the centre of gravity
ui/         Vite + React + Tailwind v4 + TanStack + Observable Plot + DuckDB-Wasm
```
