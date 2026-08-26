"""Run orchestration.

=============================================================================
PHASE 0 PLACEHOLDER. Read this before trusting any number this file produces.
=============================================================================
The stages below are not implemented yet. `_placeholder_scorecard` synthesises a
scorecard of the correct SHAPE from the run seed so that the measurement harness,
the artifact contract and the UI can be built and tested against something real.

Every number it emits is fabricated. It is wired to fail loudly rather than mislead:
`scorecard.limitations` carries a PLACEHOLDER banner, and the UI renders that banner
across the top of the dashboard. Delete this module's `_placeholder_*` functions as
phases 1-6 land; the CLI, artifact and store contracts around them stay.

Build order and acceptance criteria: INAI_SPEC.md §11.
"""

from __future__ import annotations

import platform
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from inai import __version__
from inai.config import RUNS_DIR, ResolvedConfig
from inai.eval.report import RunArtifacts
from inai.eval.scorecard import (
    ArmResult,
    BridgeMetrics,
    ConfidenceInterval,
    ExceptionBucket,
    PolicyBlock,
    ReconMetrics,
    RecoveryMetrics,
    RunMeta,
    Scorecard,
    TierResult,
)
from inai.money import pct
from inai.schema import TIER_ORDER, Arm, ExceptionClass, MatchTier
from inai.store.duckdb_store import Store

PLACEHOLDER_BANNER = (
    "PLACEHOLDER RUN — the matcher, classifier and recovery core are not implemented yet "
    "(INAI_SPEC.md §11 phases 1-6). Every figure on this scorecard is synthesised from the "
    "seed and means nothing."
)

#: What each tier actually proves. Verbatim from DATA.md §5.2 — including T0's.
TIER_PROVES: dict[MatchTier, str] = {
    MatchTier.T0_EXACT: "Nothing. Say so on the slide.",
    MatchTier.T1_DETERMINISTIC: "Baseline competence.",
    MatchTier.T2_FUZZY: "The real score.",
    MatchTier.T3_STRUCTURAL: "Genuine engineering.",
    MatchTier.T4_ADVERSARIAL: "Intellectual honesty.",
}
TIER_TARGETS: dict[MatchTier, tuple[float, float]] = {
    MatchTier.T0_EXACT: (99.0, 100.0),
    MatchTier.T1_DETERMINISTIC: (97.0, 100.0),
    MatchTier.T2_FUZZY: (80.0, 90.0),
    MatchTier.T3_STRUCTURAL: (60.0, 75.0),
    MatchTier.T4_ADVERSARIAL: (0.0, 50.0),
}
TIER_SHARE: dict[MatchTier, float] = {
    MatchTier.T0_EXACT: 0.52,
    MatchTier.T1_DETERMINISTIC: 0.24,
    MatchTier.T2_FUZZY: 0.14,
    MatchTier.T3_STRUCTURAL: 0.07,
    MatchTier.T4_ADVERSARIAL: 0.03,
}


def new_run_id(cfg: ResolvedConfig) -> str:
    """Deterministic in the parts that matter, unique in the part that doesn't."""
    return f"{cfg.run.name}-{cfg.run.seed}-{cfg.short_hash[:6]}-{uuid.uuid4().hex[:6]}"


def run(config_path: str | Path, seed: int | None = None, runs_dir: Path = RUNS_DIR) -> Path:
    """Execute one full run and return its artifact directory."""
    cfg = ResolvedConfig.resolve(config_path, seed=seed)
    run_id = new_run_id(cfg)
    out = runs_dir / run_id
    started = datetime.now(UTC)
    t0 = time.perf_counter()

    # Seeded once, then split into independent child streams. Sharing one generator
    # across stages makes output depend on stage ORDER, which breaks reproducibility
    # the moment anyone reorders anything.
    root_rng = np.random.default_rng(cfg.run.seed)
    rng_recon, rng_recovery, rng_exceptions = root_rng.spawn(3)

    store = Store(out / "run.duckdb")
    store.execute(
        "INSERT INTO runs (run_id, config_name, seed, config_hash, inai_version, "
        "started_at, n_records, hardware, llm_mode) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            run_id,
            cfg.run.name,
            cfg.run.seed,
            cfg.config_hash,
            __version__,
            started,
            cfg.run.n_records,
            _hardware(),
            cfg.run.llm_mode,
        ],
    )

    # ---- STAGES 1-3 GO HERE (phases 1-6) --------------------------------
    recon, tier_counts = _placeholder_recon(cfg, rng_recon)
    recovery = _placeholder_recovery(cfg, rng_recovery)
    exception_rows = _placeholder_exceptions(cfg, rng_exceptions, tier_counts)
    buckets = _bucket_exceptions(exception_rows, cfg.run.n_records)
    bridge = _placeholder_bridge(cfg, buckets, rng_recovery)
    blocks = _placeholder_policy_blocks(cfg, rng_recovery)
    # ---------------------------------------------------------------------

    elapsed = time.perf_counter() - t0
    finished = datetime.now(UTC)

    scorecard = Scorecard(
        meta=RunMeta(
            run_id=run_id,
            config_name=cfg.run.name,
            seed=cfg.run.seed,
            config_hash=cfg.config_hash,
            started_at=started,
            finished_at=finished,
            n_records=cfg.run.n_records,
            duration_seconds=round(elapsed, 4),
            records_per_second=round(cfg.run.n_records / max(elapsed, 1e-6), 1),
            hardware=_hardware(),
            inai_version=__version__,
            llm_mode=cfg.run.llm_mode,
        ),
        recon=recon,
        recovery=recovery,
        bridge=bridge,
        exceptions=buckets,
        unresolved_count=sum(b.count for b in buckets if b.cls is ExceptionClass.UNRESOLVED),
        policy_blocks=blocks,
        limitations=[PLACEHOLDER_BANNER, *LIMITATIONS],
    )

    artifacts = RunArtifacts(out)
    artifacts.write_scorecard(scorecard)
    artifacts.write_tier_csv(scorecard)
    artifacts.write_exceptions_csv(exception_rows)
    artifacts.append_audit([{"event": "run_complete", "run_id": run_id, "ts": finished}])

    _load_exceptions_to_store(store, run_id, exception_rows)
    # The dashboard reads this Parquet directly through DuckDB-Wasm, so it gets a flat,
    # display-ready projection: the ref LISTS collapse to their primary element for the
    # table columns, while the full lists stay for the drill-down.
    store.export_parquet(
        f"""(
            SELECT exception_id, cls, tier, ledger_ref,
                   settlement_refs[1] AS settlement_ref,
                   bank_refs[1]       AS bank_ref,
                   settlement_refs, bank_refs,
                   amount_paise, machine_reason, human_reason, routed_action
            FROM exceptions WHERE run_id = '{run_id}'
        )""",
        out / "exceptions.parquet",
    )
    store.execute("UPDATE runs SET finished_at = ? WHERE run_id = ?", [finished, run_id])
    store.close()

    runs_dir.mkdir(parents=True, exist_ok=True)
    artifacts.latest_pointer(runs_dir)
    return out


#: INAI_SPEC.md §13 — state them before a judge finds them.
LIMITATIONS: list[str] = [
    "No public three-way recon dataset exists. Ours is generated forward from known truth, "
    "then corrupted with documented failure modes. What transfers is the method, not the "
    "absolute match rate.",
    "Bank narration realism is the weakest link. Grammar derived from published NEFT/UPI "
    "formats; read T2 results as directional.",
    "Transaction spine is Brazilian (Olist). Structure transfers; amounts and rails are "
    "re-mapped to India.",
    "Recovery propensities are modelled. Absolute lift is a property of our simulator.",
    "Annoyance/churn cost is a proxy, not measured. Weakest parameter in the EV function.",
    "Regulatory constants move. Every [VERIFY] is a live check, not a one-time lookup.",
    "The uplift model needs real holdout history to train properly, which most merchants "
    "do not keep. That is itself a finding.",
]


def _hardware() -> str:
    return f"{platform.processor() or platform.machine()} / {platform.system()}"


# ---------------------------------------------------------------------------
# Placeholders — delete as phases 1-6 land.
# ---------------------------------------------------------------------------
def _placeholder_recon(
    cfg: ResolvedConfig, rng: np.random.Generator
) -> tuple[ReconMetrics, dict[MatchTier, int]]:
    n = cfg.run.n_records
    counts: dict[MatchTier, int] = {}
    remaining = n
    for tier in TIER_ORDER[:-1]:
        c = round(n * TIER_SHARE[tier])
        counts[tier] = c
        remaining -= c
    counts[MatchTier.T4_ADVERSARIAL] = max(remaining, 0)

    tiers: list[TierResult] = []
    total_matched = 0
    auto_matched = 0
    for tier in TIER_ORDER:
        lo, hi = TIER_TARGETS[tier]
        rate = (
            float(rng.uniform(lo, hi))
            if tier is not MatchTier.T4_ADVERSARIAL
            else float(rng.uniform(28.0, 46.0))
        )
        eligible = counts[tier]
        matched = round(eligible * rate / 100)
        total_matched += matched
        if tier in (MatchTier.T0_EXACT, MatchTier.T1_DETERMINISTIC, MatchTier.T2_FUZZY):
            auto_matched += matched
        tiers.append(
            TierResult(
                tier=tier,
                eligible=eligible,
                matched=matched,
                match_rate_pct=round(pct(matched, eligible), 2),
                target_pct_low=lo,
                target_pct_high=hi,
                proves=TIER_PROVES[tier],
            )
        )

    total_residual = int(rng.integers(400_000, 900_000)) * max(n // 1000, 1)
    attributed = int(total_residual * float(rng.uniform(0.86, 0.96)))
    return (
        ReconMetrics(
            tiers=tiers,
            auto_match_rate_pct=round(pct(auto_matched, n), 2),
            overall_match_rate_pct=round(pct(total_matched, n), 2),
            exception_rate_pct=round(pct(n - total_matched, n), 2),
            residual_explained_pct=round(pct(attributed, total_residual), 2),
            total_residual_paise=total_residual,
            attributed_residual_paise=attributed,
        ),
        counts,
    )


def _placeholder_recovery(cfg: ResolvedConfig, rng: np.random.Generator) -> RecoveryMetrics:
    n = cfg.run.n_records
    split = cfg.run.arms
    arms: list[ArmResult] = []
    rates = {
        Arm.AGENT: float(rng.uniform(46.0, 54.0)),
        Arm.CONTROL: float(rng.uniform(38.0, 43.0)),
        Arm.PURE_HOLDOUT: float(rng.uniform(30.0, 36.0)),
    }
    shares = {
        Arm.AGENT: split.agent,
        Arm.CONTROL: split.control,
        Arm.PURE_HOLDOUT: split.pure_holdout,
    }
    for arm, share in shares.items():
        n_acc = round(n * share)
        at_risk = n_acc * int(rng.integers(180_000, 320_000))
        recovered = int(at_risk * rates[arm] / 100)
        arms.append(
            ArmResult(
                arm=arm,
                n_accounts=n_acc,
                at_risk_paise=at_risk,
                recovered_paise=recovered,
                gross_recovery_rate_pct=round(rates[arm], 2),
                contacts_made=0 if arm is Arm.PURE_HOLDOUT else int(n_acc * rng.uniform(0.5, 2.4)),
                retries_attempted=0
                if arm is Arm.PURE_HOLDOUT
                else int(n_acc * rng.uniform(0.7, 2.9)),
                cost_incurred_paise=0
                if arm is Arm.PURE_HOLDOUT
                else int(n_acc * rng.uniform(600, 5200)),
            )
        )

    agent, control = arms[0], arms[1]
    diff = agent.gross_recovery_rate_pct - control.gross_recovery_rate_pct
    half = float(rng.uniform(1.8, 4.6))
    incremental = int(agent.at_risk_paise * diff / 100)
    inc_half = int(incremental * float(rng.uniform(0.18, 0.42)))
    return RecoveryMetrics(
        arms=arms,
        self_cure_rate_pct=arms[2].gross_recovery_rate_pct,
        baseline_rate_pct=control.gross_recovery_rate_pct,
        agent_rate_pct=agent.gross_recovery_rate_pct,
        incremental_vs_baseline_paise=incremental,
        lift_pct=round(diff / control.gross_recovery_rate_pct * 100, 2),
        rate_difference_ci=ConfidenceInterval(
            point=round(diff, 2),
            low=round(diff - half, 2),
            high=round(diff + half, 2),
            method="two_proportion_z",
            crosses_zero=(diff - half) <= 0 <= (diff + half),
        ),
        incremental_paise_ci=ConfidenceInterval(
            point=incremental,
            low=incremental - inc_half,
            high=incremental + inc_half,
            method="bootstrap_10k",
            crosses_zero=(incremental - inc_half) <= 0 <= (incremental + inc_half),
        ),
        cost_per_100_recovered_paise=int(
            agent.cost_incurred_paise / max(incremental, 1) * 100 * 100
        ),
        mde_pp=round(float(rng.uniform(4.0, 5.0)), 2),
        oracle_gap_pct=round(float(rng.uniform(58.0, 74.0)), 2),
    )


EXCEPTION_MIX: dict[ExceptionClass, float] = {
    ExceptionClass.UNAPPLIED_CASH: 0.24,
    ExceptionClass.GENUINELY_UNPAID: 0.21,
    ExceptionClass.TIMING_DIFFERENCE: 0.13,
    ExceptionClass.PARTIAL_PAYMENT: 0.09,
    ExceptionClass.FEE_TAX_VARIANCE: 0.08,
    ExceptionClass.SHORT_SETTLEMENT: 0.06,
    ExceptionClass.UNSETTLED_CAPTURE: 0.05,
    ExceptionClass.MISSING_REFUND_REVERSAL: 0.04,
    ExceptionClass.DUPLICATE_PAYMENT: 0.03,
    ExceptionClass.DISPUTE_HOLD: 0.03,
    ExceptionClass.UNRESOLVED: 0.04,
}

_ACTION_FOR: dict[ExceptionClass, str] = {
    ExceptionClass.UNAPPLIED_CASH: "cancel_dunning",
    ExceptionClass.GENUINELY_UNPAID: "silent_retry",
    ExceptionClass.SHORT_SETTLEMENT: "pg_adjustment_query",
    ExceptionClass.MISSING_REFUND_REVERSAL: "pg_adjustment_query",
    ExceptionClass.UNSETTLED_CAPTURE: "pg_adjustment_query",
    ExceptionClass.PARTIAL_PAYMENT: "whatsapp",
    ExceptionClass.FEE_TAX_VARIANCE: "pg_adjustment_query",
    ExceptionClass.DUPLICATE_PAYMENT: "credit_note",
    ExceptionClass.TIMING_DIFFERENCE: "no_action",
    ExceptionClass.DISPUTE_HOLD: "human_queue",
    ExceptionClass.UNRESOLVED: "human_queue",
}


def _placeholder_exceptions(
    cfg: ResolvedConfig, rng: np.random.Generator, tier_counts: dict[MatchTier, int]
) -> list[dict[str, Any]]:
    n_exceptions = int(cfg.run.n_records * float(rng.uniform(0.06, 0.11)))
    classes = list(EXCEPTION_MIX)
    weights = np.array([EXCEPTION_MIX[c] for c in classes])
    weights = weights / weights.sum()
    tiers = list(TIER_ORDER)
    tier_w = np.array([0.04, 0.16, 0.30, 0.28, 0.22])

    rows: list[dict[str, Any]] = []
    for i in range(n_exceptions):
        cls = classes[round(rng.choice(len(classes), p=weights))]
        tier = tiers[round(rng.choice(len(tiers), p=tier_w))]
        amount = int(rng.integers(45_000, 4_800_000))
        rows.append(
            {
                "exception_id": f"exc_{i:06d}",
                "cls": cls.value,
                "tier": tier.value,
                "ledger_ref": f"inv_{int(rng.integers(0, cfg.run.n_records)):06d}",
                "settlement_ref": f"pay_{rng.integers(10**11, 10**12)}",
                "bank_ref": f"stmt_{int(rng.integers(0, cfg.run.n_records)):06d}",
                "amount_paise": amount,
                "machine_reason": f"{cls.value.lower()} @ {tier.value}",
                "human_reason": "",
                "routed_action": _ACTION_FOR[cls],
            }
        )
    return rows


def _bucket_exceptions(rows: list[dict[str, Any]], n_records: int) -> list[ExceptionBucket]:
    agg: dict[str, dict[str, Any]] = {}
    for r in rows:
        b = agg.setdefault(r["cls"], {"count": 0, "amount": 0, "actions": {}})
        b["count"] += 1
        b["amount"] += r["amount_paise"]
        b["actions"][r["routed_action"]] = b["actions"].get(r["routed_action"], 0) + 1
    return [
        ExceptionBucket(
            cls=ExceptionClass(cls),
            count=v["count"],
            amount_paise=v["amount"],
            pct_of_batch=round(pct(v["count"], n_records), 2),
            routed_action_counts=v["actions"],
        )
        for cls, v in sorted(agg.items(), key=lambda kv: -kv[1]["count"])
    ]


def _placeholder_bridge(
    cfg: ResolvedConfig, buckets: list[ExceptionBucket], rng: np.random.Generator
) -> BridgeMetrics:
    from inai.schema import RAILS_LEAKAGE_CLASSES

    by_cls = {b.cls: b for b in buckets}
    unapplied = by_cls.get(ExceptionClass.UNAPPLIED_CASH)
    prevented_n = unapplied.count if unapplied else 0
    contact_cost = int(cfg.constant("cost.whatsapp_utility_inr") * 100)
    churn = float(cfg.constant("cost.churn_risk_per_false_contact"))
    ltv = int(cfg.constant("cost.mean_ltv_inr") * 100)
    prevented_paise = int(prevented_n * (contact_cost + churn * ltv))

    leakage = {c: by_cls[c].amount_paise for c in RAILS_LEAKAGE_CLASSES if c in by_cls}
    bounce_fee = int(cfg.constant("cost.nach_bounce_fee_inr") * 100)
    futile = int(cfg.run.n_records * float(rng.uniform(0.012, 0.028)))
    return BridgeMetrics(
        false_dunning_prevented_n=prevented_n,
        false_dunning_prevented_paise=prevented_paise,
        rails_leakage_recovered_paise=sum(leakage.values()),
        rails_leakage_by_class=leakage,
        futile_retries_avoided=futile,
        futile_retry_savings_paise=futile * bounce_fee,
    )


_RULES: list[tuple[str, str]] = [
    ("POL-RECON-001", "Unmatched-but-money-arrived -> block all dunning"),
    ("POL-CAUSE-001", "retryability == NO_RETRY -> block all retry actions"),
    ("POL-CON-001", "Voice only 09:00-18:00 payer-local"),
    ("POL-NPCI-001", "Retries per mandate per cycle <= cap"),
    ("POL-RBI-001", "Pre-debit notification >= 24h before any debit"),
    ("POL-TRAI-002", "DND payer -> transactional channels only"),
    ("POL-PTP-001", "Active promise-to-pay -> suppress contact until PTP date + grace"),
    ("POL-DIS-001", "Disputed / chargeback-in-flight -> freeze, human only"),
]


def _placeholder_policy_blocks(cfg: ResolvedConfig, rng: np.random.Generator) -> list[PolicyBlock]:
    return [
        PolicyBlock(
            rule_id=rid,
            rule_text=text,
            blocked_count=(c := round(cfg.run.n_records * float(rng.uniform(0.002, 0.05)))),
            amount_affected_paise=c * int(rng.integers(120_000, 900_000)),
        )
        for rid, text in _RULES
    ]


def _load_exceptions_to_store(store: Store, run_id: str, rows: list[dict[str, Any]]) -> None:
    for r in rows:
        store.execute(
            "INSERT INTO exceptions (run_id, exception_id, cls, tier, ledger_ref, "
            "settlement_refs, bank_refs, amount_paise, machine_reason, human_reason, "
            "routed_action) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [
                run_id,
                r["exception_id"],
                r["cls"],
                r["tier"],
                r["ledger_ref"],
                [r["settlement_ref"]],
                [r["bank_ref"]],
                r["amount_paise"],
                r["machine_reason"],
                r["human_reason"],
                r["routed_action"],
            ],
        )
