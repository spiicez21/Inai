"""Layer 2 — the real transaction spine. DATA.md §2.

Olist Brazilian E-Commerce: 99,441 orders, 103,886 payments, Sep 2016 – Oct 2018.

**Only the STRUCTURE transfers.** What we take from Brazil:

  * `payment_sequential` — one order paid with several payment methods. Real many-to-one
    behaviour that breaks naive matchers. Measured here: 2,961 of 99,441 orders (3.0%).
  * `payment_installments` — real split-payment structure, 49.4% of payments.
  * purchase → approval lag — p50 20min, p90 34.7h, p99 90h.
  * cancellation — `canceled`/`unavailable`, 1,234 orders (1.2%).

What we do NOT take: amounts, rails, or method mix. Brazil is credit-card dominant
(73.9%); India is UPI dominant. `inai/sim/localize.py` remaps all of it.

Say this in the deck, because it is a fair objection and it costs nothing to answer:
*"Only the structure transfers, not the amounts."*
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from inai.config import REPO_ROOT

SPINE_DIR = REPO_ROOT / "data" / "spine"

PAYMENTS_CSV = "olist_order_payments_dataset.csv"
ORDERS_CSV = "olist_orders_dataset.csv"
CUSTOMERS_CSV = "olist_customers_dataset.csv"

#: Statuses that mean the order was never fulfilled. Feeds C13 (cancel post-capture).
CANCELLED_STATUSES = frozenset({"canceled", "unavailable"})


class SpineUnavailable(RuntimeError):
    """Raised when the Olist CSVs are missing.

    Deliberately fatal rather than falling back to invented structure: the multi-payment
    cardinality is the single distribution that determines how hard the T3 tier is, and
    inventing it would make the tier breakdown circular.
    """


@dataclass(frozen=True, slots=True)
class SpinePayment:
    sequential: int
    payment_type: str  # credit_card | boleto | voucher | debit_card
    installments: int
    value: float  # BRL — rescaled to INR paise by `localize`, never used directly


@dataclass(frozen=True, slots=True)
class SpineOrder:
    order_id: str
    #: `customer_unique_id`, NOT `customer_id`.
    #:
    #: Olist issues a fresh `customer_id` per order, so using it as the payer identity
    #: gives every invoice its own customer — no repeat payers, no customer with two open
    #: invoices, and therefore C02 (bundle N invoices into one credit) can never fire.
    #: `customer_unique_id` is the real person: 96,096 of them across 99,441 orders.
    customer_id: str
    purchase_at: datetime
    approved_at: datetime | None
    status: str
    payments: tuple[SpinePayment, ...]

    @property
    def cancelled(self) -> bool:
        return self.status in CANCELLED_STATUSES

    @property
    def total_value(self) -> float:
        return sum(p.value for p in self.payments)


def spine_available(spine_dir: Path = SPINE_DIR) -> bool:
    return all((spine_dir / f).exists() for f in (PAYMENTS_CSV, ORDERS_CSV, CUSTOMERS_CSV))


def load_spine(
    n_orders: int,
    seed: int,
    spine_dir: Path = SPINE_DIR,
    repeat_boost: float = 6.0,
) -> list[SpineOrder]:
    """Load a seeded, reproducible sample of `n_orders` real orders.

    Sampling is by a hash of `order_id` rather than by row position, so the same seed
    selects the same orders regardless of how the CSV is ordered on disk or whether Polars
    changes its scan order between versions.
    """
    if not spine_available(spine_dir):
        raise SpineUnavailable(
            f"Olist CSVs not found in {spine_dir}. Download with:\n"
            f"  kaggle datasets download -d olistbr/brazilian-ecommerce "
            f"-p data/spine --unzip\n"
            f"Needs: {PAYMENTS_CSV}, {ORDERS_CSV}, {CUSTOMERS_CSV}. See DATA.md §2."
        )

    orders = pl.read_csv(
        spine_dir / ORDERS_CSV,
        columns=[
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
        ],
    ).with_columns(
        pl.col("order_purchase_timestamp").str.to_datetime(strict=False),
        pl.col("order_approved_at").str.to_datetime(strict=False),
    )

    # Resolve the real payer. Without this every invoice gets a unique customer.
    customers = pl.read_csv(
        spine_dir / CUSTOMERS_CSV, columns=["customer_id", "customer_unique_id"]
    )
    unique_by_customer: dict[str, str] = dict(
        zip(
            customers["customer_id"].to_list(),
            customers["customer_unique_id"].to_list(),
            strict=True,
        )
    )

    # Sample CUSTOMER-first, not order-first.
    #
    # Order-first sampling draws n orders out of 99,441, and since only 2,997 of 96,096
    # customers ever order twice, a 200-row sample essentially never contains the same
    # payer twice. That silently makes C02 (bundle N invoices into one credit) impossible
    # and removes the repeat-payer behaviour the recovery scorer keys on.
    #
    # `repeat_boost` then oversamples multi-order customers. This is a DELIBERATE deviation
    # from the spine's own distribution and belongs in the deck: Olist is consumer
    # e-commerce, where a one-off purchase is the norm, while INAI targets merchants with
    # recurring and B2B receivables, where one customer holding several open invoices is
    # ordinary. We take Olist's multi-payment *structure*, not its repeat-purchase rate.
    orders = orders.with_columns(
        pl.col("customer_id").replace_strict(unique_by_customer, default=None).alias("payer_id")
    )
    per_payer = orders.group_by("payer_id").agg(pl.len().alias("n_orders"))
    weight = pl.when(pl.col("n_orders") > 1).then(repeat_boost).otherwise(1.0)
    per_payer = per_payer.with_columns(
        (pl.col("payer_id").hash(seed=seed) % 1_000_000).cast(pl.Float64).alias("_h")
    ).with_columns((pl.col("_h") / weight).alias("_rank"))

    chosen: list[str] = []
    running = 0
    for row in per_payer.sort("_rank").iter_rows(named=True):
        if running >= n_orders:
            break
        chosen.append(row["payer_id"])
        running += int(row["n_orders"])

    orders = orders.filter(pl.col("payer_id").is_in(set(chosen))).head(n_orders)
    keep = set(orders["order_id"].to_list())

    payments = (
        pl.read_csv(spine_dir / PAYMENTS_CSV)
        .filter(pl.col("order_id").is_in(keep))
        .filter(pl.col("payment_type") != "not_defined")  # 3 rows, all zero-value
        .sort(["order_id", "payment_sequential"])
    )

    by_order: dict[str, list[SpinePayment]] = {}
    for row in payments.iter_rows(named=True):
        by_order.setdefault(row["order_id"], []).append(
            SpinePayment(
                sequential=int(row["payment_sequential"]),
                payment_type=str(row["payment_type"]),
                installments=max(int(row["payment_installments"]), 1),
                value=float(row["payment_value"]),
            )
        )

    out: list[SpineOrder] = []
    for row in orders.iter_rows(named=True):
        pays = by_order.get(row["order_id"])
        if not pays:  # a handful of orders carry no payment row at all
            continue
        out.append(
            SpineOrder(
                order_id=str(row["order_id"]),
                customer_id=str(row["payer_id"]),
                purchase_at=row["order_purchase_timestamp"],
                approved_at=row["order_approved_at"],
                status=str(row["order_status"]),
                payments=tuple(pays),
            )
        )

    # Sorted by id so downstream iteration order never depends on Polars internals.
    out.sort(key=lambda o: o.order_id)
    return out
