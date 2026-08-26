"""`inai` — everything headless.

inai run  --config configs/demo.yaml --seed 42
inai eval --run-id demo-42-a1b2c3-9f8e7d
inai constants cost.nach_bounce_fee_inr
inai verify          # list every [VERIFY] constant that is due a live re-check
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from inai import __version__
from inai.config import RUNS_DIR, ResolvedConfig
from inai.money import format_inr


def _force_utf8() -> None:
    """Windows consoles default to cp1252, which cannot encode ₹ (U+20B9).

    A rupee sign is not optional in this tool, so the stream gets reconfigured rather than
    the output degraded.
    """
    for stream in (sys.stdout, sys.stderr):
        enc = getattr(stream, "encoding", "") or ""
        if enc.lower().replace("-", "") != "utf8":
            with contextlib.suppress(AttributeError, OSError):
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]


_force_utf8()

app = typer.Typer(
    name="inai",
    help="INAI — reconciliation-first revenue recovery. Match first. Then chase.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", exists=True, help="configs/*.yaml"),
    seed: int | None = typer.Option(None, "--seed", "-s", help="Overrides the config's seed."),
) -> None:
    """Execute one full run. Writes runs/{run_id}/."""
    from inai.pipeline import run as run_pipeline

    out = run_pipeline(config, seed=seed)
    scorecard = json.loads((out / "scorecard.json").read_text(encoding="utf-8"))
    _print_scorecard(scorecard)
    console.print(f"\n[dim]artifacts →[/dim] {out}")


@app.command()
def eval(
    run_id: str = typer.Option(..., "--run-id", "-r"),
    runs_dir: Path = typer.Option(RUNS_DIR, "--runs-dir"),
) -> None:
    """Re-print the scorecard for an existing run."""
    path = runs_dir / run_id / "scorecard.json"
    if not path.exists():
        console.print(f"[red]no scorecard at {path}[/red]")
        raise typer.Exit(1)
    _print_scorecard(json.loads(path.read_text(encoding="utf-8")))


@app.command()
def constants(
    key: str = typer.Argument(None, help="Dotted key, e.g. cost.nach_bounce_fee_inr"),
    config: Path = typer.Option(Path("configs/smoke.yaml"), "--config", "-c"),
) -> None:
    """Print a calibration constant WITH its provenance. Never quote a number without it."""
    cfg = ResolvedConfig.resolve(config)
    if key is None:
        console.print_json(data=cfg.constants)
        return
    node = cfg.constants
    for part in key.split("."):
        node = node[part]
    console.print_json(data=node)


@app.command()
def verify(config: Path = typer.Option(Path("configs/smoke.yaml"), "--config", "-c")) -> None:
    """List every constant flagged `verify: true`.

    A regulatory or schema fact that moves. Run this before demo day, not once at the start.
    """
    cfg = ResolvedConfig.resolve(config)
    table = Table(title="[VERIFY] — live re-check required", header_style="bold yellow")
    table.add_column("key")
    table.add_column("value", justify="right")
    table.add_column("as_of")
    table.add_column("source", overflow="fold")

    def walk(node: object, prefix: str = "") -> None:
        if isinstance(node, dict):
            if node.get("verify") is True:
                table.add_row(
                    prefix, str(node.get("value")), str(node.get("as_of")), str(node.get("source"))
                )
                return
            for k, v in node.items():
                walk(v, f"{prefix}.{k}" if prefix else k)

    walk(cfg.constants)
    console.print(table)


@app.command()
def version() -> None:
    console.print(f"inai {__version__}")


def _print_scorecard(sc: dict[str, Any]) -> None:
    meta = sc["meta"]
    for note in sc.get("limitations", []):
        if note.startswith("PLACEHOLDER RUN"):
            console.print(f"[bold black on yellow] {note} [/]\n")

    head = Table(box=None, show_header=False)
    head.add_row("[bold]run_id[/bold]", meta["run_id"])
    head.add_row("[bold]seed[/bold]", str(meta["seed"]))
    head.add_row("[bold]config_hash[/bold]", meta["config_hash"][:16] + "…")
    head.add_row("[bold]records[/bold]", f"{meta['n_records']:,}")
    head.add_row(
        "[bold]throughput[/bold]", f"{meta['records_per_second']:,.0f} rec/s on {meta['hardware']}"
    )
    console.print(head)

    tiers = Table(title="\nMatch rate by tier — never blended", header_style="bold")
    tiers.add_column("tier")
    tiers.add_column("eligible", justify="right")
    tiers.add_column("matched", justify="right")
    tiers.add_column("rate", justify="right")
    tiers.add_column("target", justify="right")
    tiers.add_column("what it proves")
    for t in sc["recon"]["tiers"]:
        tiers.add_row(
            t["tier"],
            f"{t['eligible']:,}",
            f"{t['matched']:,}",
            f"{t['match_rate_pct']:.1f}%",
            f"{t['target_pct_low']:.0f}-{t['target_pct_high']:.0f}%",
            t["proves"],
        )
    console.print(tiers)

    rec, br = sc["recovery"], sc["bridge"]
    ci = rec["rate_difference_ci"]
    zero_note = "  [bold red]<- CROSSES ZERO[/bold red]" if ci["crosses_zero"] else ""
    out = Table(title="\nHeadline", box=None, show_header=False)
    out.add_row("self-cure (holdout)", f"{rec['self_cure_rate_pct']:.1f}%")
    out.add_row("baseline (control)", f"{rec['baseline_rate_pct']:.1f}%")
    out.add_row("agent", f"{rec['agent_rate_pct']:.1f}%")
    out.add_row("incremental vs baseline", format_inr(rec["incremental_vs_baseline_paise"]))
    out.add_row("95% CI on rate diff", f"[{ci['low']:+.1f}, {ci['high']:+.1f}] pp{zero_note}")
    out.add_row("false dunning prevented", f"{br['false_dunning_prevented_n']:,} accounts")
    out.add_row("", format_inr(br["false_dunning_prevented_paise"]))
    out.add_row("rails leakage recovered", format_inr(br["rails_leakage_recovered_paise"]))
    out.add_row("futile retries avoided", f"{br['futile_retries_avoided']:,}")
    out.add_row("unresolved, shown not hidden", f"{sc['unresolved_count']:,}")
    console.print(out)


if __name__ == "__main__":
    app()
