"""(seed, config_hash) -> identical scorecard. INAI_SPEC.md §0.5.

If this test ever goes red, the claim "re-run it yourself" on the closing slide is a lie.
Usual culprits, in order of likelihood:
  * an unseeded `random` / `np.random.*` module-level call (ruff NPY002 catches most)
  * dict iteration order leaking into a float accumulation
  * a live LLM call on a path that should be replay-only
  * a timestamp inside a hashed structure
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from inai.config import ResolvedConfig, canonical_hash
from inai.pipeline import run as run_pipeline

CONFIG = Path("configs/smoke.yaml")

#: Legitimately run-to-run varying: wall-clock, the uuid suffix, and machine speed.
VOLATILE = {
    "run_id",
    "started_at",
    "finished_at",
    "duration_seconds",
    "records_per_second",
    "hardware",
}


def _stable(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _stable(v) for k, v in node.items() if k not in VOLATILE}
    if isinstance(node, list):
        return [_stable(v) for v in node]
    return node


def _scorecard(tmp: Path, seed: int = 42) -> dict[str, Any]:
    out = run_pipeline(CONFIG, seed=seed, runs_dir=tmp)
    return json.loads((out / "scorecard.json").read_text(encoding="utf-8"))


def test_same_seed_same_scorecard(tmp_path: Path) -> None:
    a = _scorecard(tmp_path / "a")
    b = _scorecard(tmp_path / "b")
    assert canonical_hash(_stable(a)) == canonical_hash(_stable(b))


def test_different_seed_different_scorecard(tmp_path: Path) -> None:
    """Guards the opposite failure: a 'deterministic' run that ignores the seed entirely."""
    a = _scorecard(tmp_path / "a", seed=42)
    b = _scorecard(tmp_path / "b", seed=43)
    assert canonical_hash(_stable(a)) != canonical_hash(_stable(b))


def test_config_hash_is_order_independent() -> None:
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_config_hash_changes_with_seed() -> None:
    assert (
        ResolvedConfig.resolve(CONFIG, seed=42).config_hash
        != ResolvedConfig.resolve(CONFIG, seed=43).config_hash
    )


def test_scorecard_prints_its_own_provenance(tmp_path: Path) -> None:
    """Seed and config hash on the face of the scorecard, or the closing slide has nothing
    to point at (INAI_SPEC.md §12.8)."""
    meta = _scorecard(tmp_path)["meta"]
    assert meta["seed"] == 42
    assert len(meta["config_hash"]) == 64


@pytest.mark.parametrize("arm_field", ["agent", "control", "pure_holdout"])
def test_all_three_arms_present(tmp_path: Path, arm_field: str) -> None:
    """Three arms, not two. The control arm running WITHOUT reconciliation is what makes
    false dunning measurable (INAI_SPEC.md §9.1)."""
    arms = {a["arm"] for a in _scorecard(tmp_path)["recovery"]["arms"]}
    assert arm_field in arms
