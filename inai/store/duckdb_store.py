"""DuckDB store. Tables mirror `inai.schema` 1:1.

Two schemas, deliberately separated (DATA.md §5.3):
    main          — everything the pipeline may read
    ground_truth  — the answers; only the simulator writes, only the evaluator reads

The decision log is append-only. There is no UPDATE statement anywhere in this module,
and there must never be one: an audit trail you can rewrite is not an audit trail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

#: The quarantined schema. Defined HERE, not imported from `inai.sim.truth` — the store is
#: shared infrastructure and must not depend on the truth module, or the ban rule has a hole
#: in it that every other package can walk through. `inai.sim.truth` re-exports this name.
TRUTH_SCHEMA = "ground_truth"

SCHEMA_SQL = f"""
CREATE SCHEMA IF NOT EXISTS {TRUTH_SCHEMA};

CREATE TABLE IF NOT EXISTS runs (
    run_id           VARCHAR PRIMARY KEY,
    config_name      VARCHAR NOT NULL,
    seed             BIGINT  NOT NULL,
    config_hash      VARCHAR NOT NULL,
    inai_version     VARCHAR NOT NULL,
    started_at       TIMESTAMP NOT NULL,
    finished_at      TIMESTAMP,
    n_records        BIGINT,
    hardware         VARCHAR,
    llm_mode         VARCHAR
);

CREATE TABLE IF NOT EXISTS invoices (
    run_id           VARCHAR NOT NULL,
    invoice_id       VARCHAR NOT NULL,
    customer_id      VARCHAR NOT NULL,
    customer_name    VARCHAR NOT NULL DEFAULT '',
    issued_at        TIMESTAMP NOT NULL,
    due_at           TIMESTAMP NOT NULL,
    amount_paise     BIGINT  NOT NULL,
    currency         VARCHAR NOT NULL DEFAULT 'INR',
    order_id         VARCHAR,
    subscription_id  VARCHAR,
    status           VARCHAR NOT NULL,
    has_written_agreement BOOLEAN NOT NULL,
    PRIMARY KEY (run_id, invoice_id)
);

CREATE TABLE IF NOT EXISTS settlement_legs (
    run_id           VARCHAR NOT NULL,
    entity_id        VARCHAR NOT NULL,
    type             VARCHAR NOT NULL,
    debit            BIGINT  NOT NULL,
    credit           BIGINT  NOT NULL,
    amount           BIGINT  NOT NULL,
    currency         VARCHAR NOT NULL DEFAULT 'INR',
    fee              BIGINT  NOT NULL,
    tax              BIGINT  NOT NULL,
    on_hold          BOOLEAN NOT NULL DEFAULT FALSE,
    settled          BOOLEAN NOT NULL,
    created_at       TIMESTAMP NOT NULL,
    settled_at       TIMESTAMP,
    settlement_id    VARCHAR NOT NULL,
    settlement_utr   VARCHAR NOT NULL,
    order_id         VARCHAR,
    order_receipt    VARCHAR,
    method           VARCHAR NOT NULL,
    card_network     VARCHAR,
    card_issuer      VARCHAR,
    card_type        VARCHAR,
    dispute_id       VARCHAR,
    PRIMARY KEY (run_id, entity_id)
);

CREATE TABLE IF NOT EXISTS bank_credits (
    run_id            VARCHAR NOT NULL,
    statement_line_id VARCHAR NOT NULL,
    value_date        DATE    NOT NULL,
    amount_paise      BIGINT  NOT NULL,
    narration         VARCHAR NOT NULL,
    extracted_utr     VARCHAR,
    counterparty_guess VARCHAR,
    PRIMARY KEY (run_id, statement_line_id)
);

CREATE TABLE IF NOT EXISTS match_results (
    run_id           VARCHAR NOT NULL,
    ledger_ref       VARCHAR NOT NULL,
    settlement_refs  VARCHAR[] NOT NULL,
    bank_refs        VARCHAR[] NOT NULL,
    tier             VARCHAR NOT NULL,
    confidence       DOUBLE  NOT NULL,
    residual_paise   BIGINT  NOT NULL,
    explanation      VARCHAR NOT NULL,
    matched          BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS exceptions (
    run_id           VARCHAR NOT NULL,
    exception_id     VARCHAR NOT NULL,
    cls              VARCHAR NOT NULL,
    -- Difficulty tier of the record that produced this exception. Carried here so the
    -- exception list can be read by tier without re-joining match_results — the class x
    -- tier cross-tab is where the interesting structure lives (DATA.md §5.2).
    tier             VARCHAR NOT NULL,
    ledger_ref       VARCHAR,
    settlement_refs  VARCHAR[] NOT NULL,
    bank_refs        VARCHAR[] NOT NULL,
    amount_paise     BIGINT  NOT NULL,
    machine_reason   VARCHAR NOT NULL,
    human_reason     VARCHAR NOT NULL DEFAULT '',
    routed_action    VARCHAR,
    PRIMARY KEY (run_id, exception_id)
);

-- APPEND ONLY. No UPDATE, ever.
CREATE TABLE IF NOT EXISTS decisions (
    run_id                 VARCHAR NOT NULL,
    decision_id            VARCHAR NOT NULL,
    account_id             VARCHAR NOT NULL,
    ts                     TIMESTAMP NOT NULL,
    arm                    VARCHAR NOT NULL,
    source_exception       VARCHAR,
    diagnosis_root_cause   VARCHAR,
    diagnosis_retryability VARCHAR,
    diagnosis_confidence   DOUBLE,
    candidates_json        VARCHAR NOT NULL,  -- ALL scored options, incl. rejected
    chosen_action          VARCHAR,
    gate_allowed           BOOLEAN NOT NULL,
    gate_rule_id           VARCHAR,
    gate_rule_text         VARCHAR,
    gate_remediation       VARCHAR,
    executed               BOOLEAN NOT NULL,
    outcome                VARCHAR,
    amount_recovered_paise BIGINT NOT NULL DEFAULT 0,
    cost_incurred_paise    BIGINT NOT NULL DEFAULT 0,
    cost_avoided_paise     BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, decision_id)
);

-- The answers. Written by inai/sim only, read by inai/eval only.
CREATE TABLE IF NOT EXISTS {TRUTH_SCHEMA}.truth_links (
    run_id           VARCHAR NOT NULL,
    ledger_ref       VARCHAR NOT NULL,
    settlement_refs  VARCHAR[] NOT NULL,
    bank_refs        VARCHAR[] NOT NULL,
    difficulty_tier  VARCHAR NOT NULL,
    operators_fired  VARCHAR[] NOT NULL,
    latent_state     VARCHAR NOT NULL,
    recoverable_by_perfect_policy BOOLEAN NOT NULL,
    PRIMARY KEY (run_id, ledger_ref)
);
"""


class Store:
    """Thin wrapper. Deliberately thin — DuckDB's own API is good, an ORM here would only
    hide the SQL a reviewer needs to read."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.path)
        self.con.execute(SCHEMA_SQL)

    def sql(self, query: str, params: list[Any] | None = None) -> duckdb.DuckDBPyRelation:
        return self.con.sql(query, params=params) if params else self.con.sql(query)

    def execute(self, query: str, params: list[Any] | None = None) -> None:
        self.con.execute(query, params or [])

    def export_parquet(self, table: str, out_path: str | Path) -> None:
        """Export one table to Parquet — this is what DuckDB-Wasm loads in the browser."""
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        posix = Path(out_path).as_posix()
        self.con.execute(f"COPY (SELECT * FROM {table}) TO '{posix}' (FORMAT PARQUET)")

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
