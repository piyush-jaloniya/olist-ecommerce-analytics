"""Export the star-schema tables for Power BI."""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path

LOGGER = logging.getLogger(__name__)

EXPORT_TABLES = [
    "dim_date",
    "dim_customer",
    "dim_product",
    "dim_seller",
    "fact_orders",
    "fact_order_items",
    "fact_order_payments",
]


class ExportError(RuntimeError):
    """Raised when an export cannot be verified."""


def export_star_tables(star_path: Path, output_dir: Path) -> list[Path]:
    """Export all star tables to CSV files and verify their row counts."""
    if not star_path.exists():
        raise FileNotFoundError(
            f"Star database does not exist: {star_path}. "
            "Run `python run_pipeline.py model` first."
        )

    tables: list[tuple[str, list[str], list[tuple[object, ...]]]] = []
    expected_counts: dict[str, int] = {}
    connection = sqlite3.connect(star_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for table in EXPORT_TABLES:
            cursor = connection.execute(f"SELECT * FROM {table} ORDER BY 1")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            expected_counts[table] = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            tables.append((table, columns, rows))
    finally:
        # The read-only connection prevents an export from changing the model database.
        connection.close()

    # Read every table before writing so a later database error cannot create partial output.
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for table, columns, rows in tables:
        output_path = output_dir / f"{table}.csv"
        with output_path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(columns)
            writer.writerows(
                ("" if value is None else value for value in row)
                for row in rows
            )
        written_paths.append(output_path)

    verify_export_counts(output_dir, expected_counts)
    for table, expected in expected_counts.items():
        LOGGER.info("%s.csv: %s rows", table, expected)
    return written_paths


def verify_export_counts(output_dir: Path, expected_counts: dict[str, int]) -> None:
    """Verify exported data rows by parsing each CSV rather than counting lines."""
    for table, expected in expected_counts.items():
        path = output_dir / f"{table}.csv"
        found = 0
        if path.exists():
            with path.open("r", encoding="utf-8", newline="") as input_file:
                reader = csv.reader(input_file)
                next(reader, None)
                found = sum(1 for _ in reader)
        if found != expected:
            raise ExportError(f"{table}.csv: expected {expected} rows, found {found}")
