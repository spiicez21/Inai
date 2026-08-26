"""Generate → corrupt → persist. The Phase 1 entry point.

DATA.md §5:

    STEP 1  generate the chain forward from truth
    STEP 2  compute the real money chain, paise-exact
    STEP 3  apply corruption operators, recording which fired
    STEP 4  hand the corrupted artifacts to the matcher, score against STEP 1

Steps 1–3 live here. Step 4 is Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from inai.config import ResolvedConfig
from inai.schema import MatchTier
from inai.sim.chain import Batch
from inai.sim.corrupt import corrupt
from inai.sim.generate import generate
from inai.sim.truth import TruthLink


@dataclass(frozen=True, slots=True)
class BuildResult:
    batch: Batch
    truth: list[TruthLink]

    @property
    def tier_counts(self) -> dict[MatchTier, int]:
        counts = dict.fromkeys(MatchTier, 0)
        for link in self.truth:
            counts[link.difficulty_tier] += 1
        return counts

    @property
    def operator_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for link in self.truth:
            for op in link.operators_fired:
                counts[op] = counts.get(op, 0) + 1
        return dict(sorted(counts.items()))


def build(cfg: ResolvedConfig, rng: np.random.Generator) -> BuildResult:
    """One batch, generated then corrupted, with ground truth recorded."""
    rng_generate, rng_corrupt = rng.spawn(2)

    batch = generate(cfg, rng_generate)
    batch = corrupt(batch, cfg.run.corruption.model_dump(), rng_corrupt)

    truth = [
        TruthLink(
            ledger_ref=chain.invoice.invoice_id,
            settlement_refs=tuple(leg.entity_id for leg in chain.legs),
            bank_refs=(chain.bank_ref,) if chain.bank_ref else (),
            difficulty_tier=chain.difficulty_tier,
            operators_fired=chain.operators_fired,
            latent_state=chain.latent_state,
            recoverable_by_perfect_policy=chain.latent_state.recoverable,
        )
        for chain in batch.chains
    ]
    return BuildResult(batch=batch, truth=truth)
