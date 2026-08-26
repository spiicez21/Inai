"""Run configuration and the reproducibility contract.

INAI_SPEC.md §0.5: `(seed, config_hash) -> identical scorecard`.

`config_hash` is the SHA-256 of the *resolved* config — constants.yaml merged with the run
config — serialised canonically (sorted keys, no whitespace). It goes on the face of the
scorecard so a judge can re-run the exact same thing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
CONSTANTS_PATH = REPO_ROOT / "config" / "constants.yaml"
RUNS_DIR = REPO_ROOT / "runs"


def canonical_hash(obj: Any) -> str:
    """Order-independent, whitespace-independent hash of a JSON-able structure."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ArmSplit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: float = 0.70
    control: float = 0.20
    pure_holdout: float = 0.10

    def validate_sums_to_one(self) -> None:
        total = self.agent + self.control + self.pure_holdout
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"arm split must sum to 1.0, got {total}")


class CorruptionRates(BaseModel):
    """Application rate per corruption operator (DATA.md §5.1). Keys are C01…C14."""

    model_config = ConfigDict(extra="allow")

    C01: float = 0.10  # strip remittance reference          -> T2
    C02: float = 0.06  # bundle N invoices into one credit   -> T3
    C03: float = 0.05  # split one invoice across payments   -> T3
    C04: float = 0.12  # shift settlement T+1…T+7            -> T1
    C05: float = 0.08  # perturb fee ±δ                      -> T1
    C06: float = 0.02  # drop a refund reversal              -> T1
    C07: float = 0.12  # mangle / truncate narration         -> T2
    C08: float = 0.02  # pay from parent-company account     -> T4
    C09: float = 0.01  # duplicate a credit                  -> T4
    C10: float = 0.02  # unexplained deduction               -> T4
    C11: float = 0.02  # capture without settlement          -> T1
    C12: float = 0.01  # chargeback mid-flight               -> T1
    C13: float = 0.02  # cancel invoice post-capture         -> T3
    C14: float = 0.06  # mixed-language / casing narration   -> T2


class RunConfig(BaseModel):
    """A `configs/*.yaml` file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    n_records: int = Field(gt=0)
    seed: int = 42
    description: str = ""
    arms: ArmSplit = Field(default_factory=ArmSplit)
    corruption: CorruptionRates = Field(default_factory=CorruptionRates)
    llm_mode: Literal["replay", "live", "off"] = "replay"
    tolerance_paise: int = 100  # ±₹1, INAI_SPEC.md §6.2 T1

    @classmethod
    def load(cls, path: str | Path) -> RunConfig:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(raw)


class ResolvedConfig(BaseModel):
    """Run config + calibration constants, together. This is what gets hashed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run: RunConfig
    constants: dict[str, Any]

    @classmethod
    def resolve(cls, config_path: str | Path, seed: int | None = None) -> ResolvedConfig:
        run = RunConfig.load(config_path)
        if seed is not None:
            run = run.model_copy(update={"seed": seed})
        run.arms.validate_sums_to_one()
        constants = yaml.safe_load(CONSTANTS_PATH.read_text(encoding="utf-8"))
        return cls(run=run, constants=constants)

    @property
    def config_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))

    @property
    def short_hash(self) -> str:
        return self.config_hash[:12]

    def constant(self, dotted_key: str) -> Any:
        """`cfg.constant("cost.nach_bounce_fee_inr")` -> the `value` field.

        Every constant in config/constants.yaml carries value/unit/source/as_of/verify.
        Reading `.value` through here means no caller ever hardcodes a number.
        """
        node: Any = self.constants
        for part in dotted_key.split("."):
            node = node[part]
        return node["value"] if isinstance(node, dict) and "value" in node else node
