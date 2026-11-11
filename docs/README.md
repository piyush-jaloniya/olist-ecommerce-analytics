# Documentation

Generated and maintained project documentation belongs here. The Phase 1 data-quality
report is generated with:

```powershell
python run_pipeline.py profile
```

## Interactive frontend dashboard

Generate the browser dashboard data after rebuilding the star database:

```powershell
python run_pipeline.py dashboard
python -m http.server 8000 --directory frontend
```

Open `http://localhost:8000` in a browser. The dashboard has three views:

- **Overview:** revenue, orders, average order value, repeat-buyer rate, monthly trends,
  year-over-year growth, payment mix, delivery timing, and category ranking.
- **Products & categories:** Pareto concentration, category revenue, freight burden proxy,
  and category detail.
- **Customers & delivery:** repeat-order distribution, cohort retention, state delivery
  performance, seller delivery performance, and review score by delivery timing.

The year and category controls are interactive. The year filter changes trend metrics;
the category filter narrows product/category detail only. Product, state, and seller tables
also support search, sorting, and row limits. A generated timestamp is shown in the header.
All displayed datasets are generated from the read-only star database and reuse the ten
validated SQL analysis queries, so the frontend remains consistent with the analysis CSVs
and future Power BI model. `frontend/data/metadata.json` records the static export contract
and row counts.

Chart.js is vendored in `frontend/js/vendor/`, so the static dashboard does not require
network access after the repository is downloaded.
