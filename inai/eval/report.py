"""Artifact writer. INAI_SPEC.md §9.7.

Every run writes a self-contained directory:

    runs/{run_id}/
        scorecard.json            <- the face of the run: seed + config_hash printed on it
        match_rates_by_tier.csv
        exceptions.csv
        exceptions.parquet        <- what DuckDB-Wasm loads in the browser
        decisions.parquet
        audit.jsonl               <- append-only decision log, one JSON object per line

Artifacts-first is a design decision, not a convenience. The UI reads these files directly;
there is no server on the critical path, so a dead process cannot take the demo with it.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from inai.eval.scorecard import Scorecard


class RunArtifacts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    # -- scorecard ---------------------------------------------------------
    def write_scorecard(self, scorecard: Scorecard) -> Path:
        path = self.root / "scorecard.json"
        path.write_text(
            json.dumps(scorecard.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    # -- tier table --------------------------------------------------------
    def write_tier_csv(self, scorecard: Scorecard) -> Path:
        path = self.root / "match_rates_by_tier.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["tier", "eligible", "matched", "match_rate_pct", "target", "proves"])
            for t in scorecard.recon.tiers:
                w.writerow(
                    [
                        t.tier.value,
                        t.eligible,
                        t.matched,
                        f"{t.match_rate_pct:.2f}",
                        f"{t.target_pct_low:.0f}-{t.target_pct_high:.0f}",
                        t.proves,
                    ]
                )
        return path

    # -- exceptions --------------------------------------------------------
    def write_exceptions_csv(self, rows: list[dict[str, Any]]) -> Path:
        path = self.root / "exceptions.csv"
        if not rows:
            path.write_text("", encoding="utf-8")
            return path
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        return path

    # -- append-only audit log --------------------------------------------
    def append_audit(self, records: list[dict[str, Any]]) -> Path:
        path = self.root / "audit.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        return path

    def latest_pointer(self, runs_dir: Path) -> Path:
        """`runs/latest.json` — what the UI opens when no run_id is in the URL."""
        pointer = runs_dir / "latest.json"
        pointer.write_text(json.dumps({"run_id": self.root.name}, indent=2), encoding="utf-8")
        return pointer
