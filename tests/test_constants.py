"""Every constant is sourced. INAI_SPEC.md §0.2: "Do not invent numbers."

This test is why a teammate cannot quietly drop a magic number into constants.yaml at 3am.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from inai.config import CONSTANTS_PATH, ResolvedConfig

REQUIRED_FIELDS = {"value", "unit", "source", "as_of", "verify"}


def _leaves(node: Any, prefix: str = "") -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    if isinstance(node, dict):
        if "value" in node:
            out.append((prefix, node))
        else:
            for k, v in node.items():
                out += _leaves(v, f"{prefix}.{k}" if prefix else k)
    return out


ALL_CONSTANTS = _leaves(yaml.safe_load(CONSTANTS_PATH.read_text(encoding="utf-8")))


def test_constants_file_is_not_empty() -> None:
    assert len(ALL_CONSTANTS) > 40, "constants.yaml looks truncated"


@pytest.mark.parametrize("key,entry", ALL_CONSTANTS, ids=[k for k, _ in ALL_CONSTANTS])
def test_every_constant_carries_provenance(key: str, entry: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - set(entry)
    assert not missing, f"{key} is missing {sorted(missing)} — see INAI_SPEC.md §3"
    assert isinstance(entry["verify"], bool), f"{key}: verify must be a bool"
    assert str(entry["source"]).strip(), f"{key}: source must not be blank"


def test_verify_flagged_constants_are_discoverable() -> None:
    """`inai verify` must surface something, or the [VERIFY] discipline is decorative."""
    flagged = [k for k, e in ALL_CONSTANTS if e["verify"] is True]
    assert flagged, "no constants flagged verify:true — regulatory facts move"
    assert "rbi.pre_debit_notification_hours" in flagged
    assert "npci.retry_cap_per_cycle" in flagged


def test_the_most_load_bearing_constant_is_present() -> None:
    """The NACH bounce fee converts 'never retry a revoked mandate' from a vague efficiency
    claim into rupees (INAI_SPEC.md §3.4)."""
    cfg = ResolvedConfig.resolve(Path("configs/smoke.yaml"))
    fee = cfg.constant("cost.nach_bounce_fee_inr")
    assert 350.0 <= fee <= 500.0


def test_msme_derived_rates_are_internally_consistent() -> None:
    """3x bank rate, compounded monthly. INAI_SPEC.md §3.7."""
    cfg = ResolvedConfig.resolve(Path("configs/smoke.yaml"))
    bank = cfg.constant("msme.rbi_bank_rate_pct")
    nominal = cfg.constant("msme.nominal_rate_pct")
    effective = cfg.constant("msme.effective_rate_pct")
    assert nominal == pytest.approx(bank * 3, abs=1e-9)
    assert effective == pytest.approx(((1 + nominal / 100 / 12) ** 12 - 1) * 100, abs=0.01)


def test_llm_is_not_pinned_to_a_dead_model() -> None:
    """INAI_SPEC.md §4 named claude-sonnet-4-6. Model IDs age; this pin is [VERIFY]."""
    cfg = ResolvedConfig.resolve(Path("configs/smoke.yaml"))
    assert cfg.constant("llm.model").startswith("claude-")
