"""GROUND TRUTH. The only module that knows the answer.

DATA.md §5.3 — the ground-truth contract:

    FORBIDDEN: inai/core/**, inai/match/**, inai/classify.py importing inai.sim.truth
    ENFORCED:  ruff TID251 banned-api (pyproject.toml) + tests/test_no_truth_leak.py, in CI

Truth precedes corruption, so ground truth is correct by construction — no hand-labelling,
no annotator disagreement, no "we eyeballed 200 rows". Writes to a SEPARATE DuckDB schema
(`ground_truth`) so a stray `SELECT *` in the main schema cannot reach it.

Only `inai/sim/**` and `inai/eval/**` may import this. The evaluator scores against it;
nothing that makes a decision may see it.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from inai.schema import MatchTier
from inai.store.duckdb_store import TRUTH_SCHEMA

__all__ = ["LATENT_STATE_PRIOR", "TRUTH_SCHEMA", "LatentState", "TruthLink"]


class LatentState(StrEnum):
    """Hidden recovery states (DATA.md §5.3). Owning these labels is what makes the
    oracle gap computable for free."""

    #: ~35%. Recovers in 14 days with or without intervention. Contacting them costs money
    #: and buys nothing. This is the population that inflates every vendor benchmark.
    SELF_CURING = "self_curing"
    #: ~20%. Recovers only if contacted on a responsive channel in their window.
    #: The only population where outreach creates value.
    PERSUADABLE = "persuadable"
    #: ~15%. Recovers on a correctly-timed retry; outreach is irrelevant and mildly annoying.
    RETRY_ONLY = "retry_only"
    #: ~15%. Hard decline. No retry ever works. Needs re-auth or amendment.
    UNREACHABLE = "unreachable"
    #: ~15%. Won't recover this cycle by any means. Correct action is early write-off.
    HOPELESS = "hopeless"


LATENT_STATE_PRIOR: dict[LatentState, float] = {
    LatentState.SELF_CURING: 0.35,
    LatentState.PERSUADABLE: 0.20,
    LatentState.RETRY_ONLY: 0.15,
    LatentState.UNREACHABLE: 0.15,
    LatentState.HOPELESS: 0.15,
}


class TruthLink(BaseModel):
    """One known-correct link in the chain: invoice -> order -> payment(s) -> leg(s) -> credit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ledger_ref: str
    settlement_refs: tuple[str, ...]
    bank_refs: tuple[str, ...]
    #: A record's tier is the HARDEST tier among the corruption operators that fired on it.
    difficulty_tier: MatchTier
    operators_fired: tuple[str, ...]  # C01…C14
    latent_state: LatentState
    #: True recoverability under a perfect policy — the denominator of the oracle gap.
    recoverable_by_perfect_policy: bool
