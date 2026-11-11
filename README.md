# Olist Analytics Pipeline

End-to-end analytics project built on the public Olist Brazilian e-commerce dataset:

```text
Raw Kaggle CSVs
      |
      v
Python ETL and validation
      |
      v
SQLite staging database
      |
      v
Validated SQLite star schema
      |
      +--> SQL analysis CSVs
      +--> Interactive HTML/CSS/JavaScript dashboard
      `--> Power BI handoff package
```

## What is included

- Modular Python extraction, transformation, validation, loading, and reconciliation.
- SQLite star schema with order-, item-, payment-, customer-, product-, seller-, and date-level
  grains.
- Ten read-only SQL analyses covering revenue trends, year-over-year growth, category and freight
  performance, delivery/reviews, repeat buyers, cohorts, states, sellers, and payments.
- Responsive static dashboard with three interactive views:
  - Overview
  - Products & categories
  - Customers & delivery
- Power BI model, DAX measures, build guide, and validation checklist for the later Power BI phase.

## Setup

Use Python 3.11.9 and place the nine Olist Kaggle CSV files in `data/raw/`. The raw files,
processed databases, and generated Power BI exports are intentionally gitignored.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the pipeline from the repository root:

```powershell
python run_pipeline.py profile
python run_pipeline.py etl
python run_pipeline.py model
python run_pipeline.py analyze
python run_pipeline.py dashboard
```

The stages are intentionally separate. `model` atomically replaces the star database only after
its reconciliation checks pass. `analyze` and `dashboard` open the star database read-only.

## Run the dashboard

After running the `dashboard` stage, serve the `frontend` directory over HTTP:

```powershell
python -m http.server 8000 --directory frontend
```

Open <http://localhost:8000>. Browser `file://` loading is not supported because the dashboard
fetches generated JSON files.

Chart.js is vendored in `frontend/js/vendor/`, so the dashboard works offline once the
repository is downloaded. The data files in `frontend/data/` are generated from the same
validated SQL definitions used by the analysis CSVs and the future Power BI report.

## Verified headline findings

- 96,478 delivered orders generated R$13,221,498.11 in item-price revenue.
- January-August 2018 orders grew 135.1% and delivered revenue grew 141.1% versus 2017.
- Repeat buyers were 2,801 of 93,358 buyers (3.0%).
- Delivered orders arriving at least one day late averaged a 2.27 review score versus 4.29 for
  orders delivered on time or early.
- The top ten categories generated 62.43% of delivered revenue.
- Credit cards represented 78.46% of delivered payment value.

## Validation

The project has no dependency on a web framework. Focused regression tests use the Python standard
library:

```powershell
python -m unittest discover -s tests -v
```

The tests cover dashboard export row counts, verified headline totals, field-for-field parity
with the analysis CSVs, read-only repeatability, and missing-database failure handling.

## Project documentation

- `docs/README.md` — dashboard usage
- `docs/data_quality_report.md` — raw-data profiling
- `docs/star_schema.md` — model grain, columns, and ER diagram
- `powerbi/BUILD_GUIDE.md` — later Power BI implementation
- `powerbi/VALIDATION.md` — Power BI reconciliation checklist
- `CLAUDE.md` — detailed project context and verified status
