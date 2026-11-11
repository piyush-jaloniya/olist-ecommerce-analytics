"""Run the currently implemented pipeline stages."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from etl.extract import extract_tables
from etl.analyze import run_analysis
from etl.dashboard import export_dashboard_data
from etl.export import export_star_tables
from etl.load import load_tables
from etl.model import build_star
from etl.profile_data import main as profile_data
from etl.reconcile import reconcile_tables
from etl.transform import transform_tables
from etl.validate import validate_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Olist analytics pipeline.")
    parser.add_argument(
        "stage",
        choices=["profile", "etl", "model", "analyze", "export", "dashboard"],
        help="Pipeline stage to run.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.stage == "profile":
        profile_data()
    elif args.stage == "etl":
        project_root = Path(__file__).resolve().parent
        extracted = extract_tables(project_root / "data" / "raw")
        transformed = transform_tables(extracted)
        validate_tables(transformed)
        database_path = load_tables(transformed, project_root / "data" / "processed")
        reconcile_tables(extracted, transformed, database_path)
    elif args.stage == "model":
        project_root = Path(__file__).resolve().parent
        processed = project_root / "data" / "processed"
        build_star(
            processed / "olist_staging.sqlite",
            processed / "olist_star.sqlite",
            project_root / "sql",
        )
    elif args.stage == "analyze":
        project_root = Path(__file__).resolve().parent
        run_analysis(
            project_root / "data" / "processed" / "olist_star.sqlite",
            project_root / "sql" / "analysis",
            project_root / "docs" / "analysis",
        )
    elif args.stage == "export":
        project_root = Path(__file__).resolve().parent
        export_star_tables(
            project_root / "data" / "processed" / "olist_star.sqlite",
            project_root / "data" / "processed" / "powerbi",
        )
    elif args.stage == "dashboard":
        project_root = Path(__file__).resolve().parent
        export_dashboard_data(
            project_root / "data" / "processed" / "olist_star.sqlite",
            project_root / "frontend" / "data",
            project_root / "sql" / "analysis",
        )


if __name__ == "__main__":
    main()
