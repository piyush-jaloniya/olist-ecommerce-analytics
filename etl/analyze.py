"""Run SQL analysis queries against the read-only star database."""

from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class AnalysisError(RuntimeError):
    """Raised when an analysis query cannot be completed."""


def run_analysis(star_path: Path, sql_dir: Path, output_dir: Path) -> list[Path]:
    """Run all analysis queries, then write their results to CSV files."""
    if not star_path.exists():
        raise FileNotFoundError(
            f"Star database does not exist: {star_path}. "
            "Run `python run_pipeline.py model` first."
        )

    query_paths = sorted(sql_dir.glob("[0-9][0-9]_*.sql"))
    if not query_paths:
        raise FileNotFoundError(
            f"No analysis SQL files found in {sql_dir} matching [0-9][0-9]_*.sql."
        )

    connection = sqlite3.connect(star_path.resolve().as_uri() + "?mode=ro", uri=True)
    results: list[tuple[Path, list[str], list[tuple[object, ...]]]] = []
    try:
        for query_path in query_paths:
            try:
                cursor = connection.execute(query_path.read_text(encoding="utf-8"))
            except sqlite3.Error as error:
                raise AnalysisError(f"{query_path.name}: {error}") from error
            if cursor.description is None:
                raise AnalysisError(f"{query_path.name}: file contains no SELECT query")
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            LOGGER.info("%s: %s rows", query_path.name, len(rows))
            if not rows:
                raise AnalysisError(f"{query_path.name}: query returned zero rows")
            results.append((query_path, columns, rows))
    finally:
        connection.close()

    # Do not write partial output if a later query fails.
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for query_path, columns, rows in results:
        output_path = output_dir / f"{query_path.stem}.csv"
        with output_path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.writer(output_file, lineterminator="\n")
            writer.writerow(columns)
            writer.writerows(
                ("" if value is None else value for value in row)
                for row in rows
            )
        written_paths.append(output_path)
    return written_paths
