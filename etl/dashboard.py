"""Export dashboard-ready JSON from the validated star database."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class DashboardExportError(RuntimeError):
    """Raised when dashboard data cannot be exported."""


OVERVIEW_QUERY = """
    WITH buyer_orders AS (
        SELECT dc.customer_unique_id,
               COUNT(DISTINCT fo.order_key) AS delivered_orders
        FROM fact_orders AS fo
        JOIN dim_customer AS dc ON dc.customer_key = fo.customer_key
        WHERE fo.is_delivered = 1
        GROUP BY dc.customer_unique_id
    ),
    buyer_summary AS (
        SELECT COUNT(*) AS buyers,
               SUM(CASE WHEN delivered_orders >= 2 THEN 1 ELSE 0 END)
                   AS repeat_buyers
        FROM buyer_orders
    ),
    order_summary AS (
        SELECT
            COUNT(DISTINCT CASE WHEN fo.is_delivered = 1 THEN fo.order_key END)
                AS delivered_orders,
            ROUND(SUM(CASE WHEN fo.is_delivered = 1
                           THEN fo.items_price_total ELSE 0 END), 2)
                AS delivered_revenue,
            ROUND(SUM(CASE WHEN fo.is_delivered = 1
                           THEN fo.items_freight_total ELSE 0 END), 2)
                AS delivered_freight,
            ROUND(SUM(CASE WHEN fo.is_delivered = 1
                           THEN fo.items_price_total ELSE 0 END)
                  / NULLIF(SUM(fo.is_delivered), 0), 2)
                AS average_order_value,
            ROUND(100.0 * SUM(CASE WHEN fo.is_delivered = 1 AND fo.is_late = 1
                                   THEN 1 ELSE 0 END)
                  / NULLIF(SUM(CASE WHEN fo.is_delivered = 1
                                    AND fo.delivery_delay_days IS NOT NULL
                                    THEN 1 ELSE 0 END), 0), 1)
                AS late_rate_pct
        FROM fact_orders AS fo
    )
    SELECT os.delivered_orders,
           os.delivered_revenue,
           os.delivered_freight,
           os.average_order_value,
           bs.buyers,
           bs.repeat_buyers,
           os.late_rate_pct
    FROM order_summary AS os
    CROSS JOIN buyer_summary AS bs
"""

ANALYSIS_DATASETS = {
    "monthly": "01_monthly_revenue_orders.sql",
    "yoy": "02_yoy_growth.sql",
    "categories": "03_category_performance.sql",
    "category_freight": "04_category_freight_burden.sql",
    "delivery_delay": "05_delay_vs_review.sql",
    "repeat": "06_repeat_rate.sql",
    "cohort": "07_cohort_retention.sql",
    "states": "08_state_delivery_performance.sql",
    "sellers": "09_seller_delivery_performance.sql",
    "payment_mix": "10_payment_mix.sql",
}

EXPECTED_COLUMNS = {
    "overview": (
        "delivered_orders", "delivered_revenue", "delivered_freight",
        "average_order_value", "buyers", "repeat_buyers", "late_rate_pct",
    ),
    "monthly": (
        "year_month", "orders_placed", "delivered_orders", "delivered_revenue",
        "delivered_freight", "avg_order_value", "revenue_mom_growth_pct",
    ),
    "yoy": (
        "year", "orders_placed", "delivered_orders", "delivered_revenue",
        "delivered_freight", "avg_order_value", "orders_growth_pct", "revenue_growth_pct",
    ),
    "categories": (
        "category", "items_sold", "orders", "revenue", "avg_item_price",
        "freight", "revenue_share_pct", "cumulative_share_pct", "revenue_rank",
    ),
    "category_freight": (
        "category", "items_sold", "revenue", "freight", "avg_freight_per_item",
        "freight_pct_of_price", "meets_min_volume", "freight_burden_rank",
    ),
    "delivery_delay": (
        "bucket_order", "delay_bucket", "orders", "avg_review_score",
        "pct_low_reviews", "pct_five_star", "avg_delay_days",
    ),
    "repeat": (
        "bucket_order", "orders_per_person", "people", "pct_of_people",
        "orders", "pct_of_orders", "revenue", "pct_of_revenue",
    ),
    "cohort": (
        "cohort_month", "people", "same_day_order_people", "eligible_30d",
        "returned_30d", "return_rate_30d_pct", "eligible_90d", "returned_90d",
        "return_rate_90d_pct", "eligible_180d", "returned_180d", "return_rate_180d_pct",
    ),
    "states": (
        "customer_state", "delivered_orders", "orders_with_delay", "late_orders",
        "late_rate_pct", "avg_delay_days", "avg_review_score", "delivered_revenue",
        "revenue_share_pct", "meets_min_volume", "late_rate_rank",
    ),
    "sellers": (
        "seller_id", "seller_state", "delivered_orders", "shared_orders",
        "orders_with_delay", "late_orders", "late_rate_pct", "avg_delay_days",
        "avg_review_score", "revenue", "meets_min_volume", "late_rate_rank",
    ),
    "payment_mix": (
        "section_order", "section", "group_order", "payment_group", "payments",
        "pct_of_payments", "orders", "payment_value", "pct_of_value", "avg_payment_value",
    ),
}


def _read_query(
    connection: sqlite3.Connection,
    query: str,
    dataset_name: str,
) -> list[dict[str, Any]]:
    cursor = connection.execute(query)
    columns = [column[0] for column in cursor.description or ()]
    expected = EXPECTED_COLUMNS[dataset_name]
    if tuple(columns) != expected:
        raise DashboardExportError(
            f"{dataset_name}: expected columns {expected}, found {tuple(columns)}"
        )
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def export_dashboard_data(
    star_path: Path,
    output_dir: Path,
    sql_dir: Path | None = None,
) -> list[Path]:
    """Export all dashboard datasets after reading the star database successfully."""
    if not star_path.exists():
        raise FileNotFoundError(
            f"Star database does not exist: {star_path}. "
            "Run `python run_pipeline.py model` first."
        )

    analysis_dir = sql_dir or Path(__file__).resolve().parents[1] / "sql" / "analysis"
    queries: dict[str, str] = {"overview": OVERVIEW_QUERY}
    for dataset_name, query_name in ANALYSIS_DATASETS.items():
        query_path = analysis_dir / query_name
        if not query_path.exists():
            raise FileNotFoundError(f"Dashboard analysis query does not exist: {query_path}")
        queries[dataset_name] = query_path.read_text(encoding="utf-8")

    connection = sqlite3.connect(star_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        datasets = {
            name: _read_query(connection, query, name)
            for name, query in queries.items()
        }
    except sqlite3.Error as error:
        raise DashboardExportError(f"Could not query the star database: {error}") from error
    finally:
        connection.close()

    if not datasets["overview"] or len(datasets["overview"]) != 1:
        raise DashboardExportError("Overview query did not return exactly one row.")
    empty_datasets = [name for name, rows in datasets.items() if not rows]
    if empty_datasets:
        raise DashboardExportError(
            f"Dashboard queries returned no rows: {', '.join(empty_datasets)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for name, rows in datasets.items():
        output_path = output_dir / f"{name}.json"
        output_path.write_text(
            json.dumps(rows, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        written_paths.append(output_path)
        LOGGER.info("%s: %s rows", output_path.name, len(rows))

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "data/processed/olist_star.sqlite",
        "source_stage": "validated SQLite star schema",
        "static_export": True,
        "dataset_count": len(datasets),
        "datasets": {
            name: {
                "file": f"{name}.json",
                "rows": len(rows),
                "columns": list(EXPECTED_COLUMNS[name]),
            }
            for name, rows in datasets.items()
        },
    }
    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    written_paths.append(metadata_path)
    LOGGER.info("%s: metadata written", metadata_path.name)
    return written_paths
