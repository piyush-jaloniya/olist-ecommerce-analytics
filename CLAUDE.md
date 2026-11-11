# Olist analytics pipeline

> Live context for AI coding agents. Keep it synchronized with the repository.
> Never mark work complete unless it is implemented AND verified.
> "Verified" = run and checked against an independent reference (Claude re-runs
> the code in a sandbox matching Python 3.11.9 / pandas 3.0.2).
> "Reported" = stated by the local coding assistant only.

## Overview
End-to-end analytics pipeline on the public Olist Brazilian e-commerce dataset (nine
Kaggle CSVs): Python ETL -> SQLite star schema -> SQL analysis -> Power BI dashboard.
Portfolio project for a Data Analyst resume. The owner must be able to explain every
cleaning and modeling decision, so prefer readable code and documented reasoning.
Business questions: revenue/order trends; category revenue, margin and freight;
delivery delay vs review score; repeat-customer rate and cohorts; state/seller
delivery performance; payment-method mix.

## Working mode
Owner runs everything locally (Windows, VS Code). Claude (chat) is the architect and
reviewer: it writes scoped implementation prompts with acceptance criteria and reviews
reports critically. GitHub Copilot implements locally and reports exactly what it did.
The local repo is the source of truth. Do not redesign existing behaviour without
explaining why. Stop at phase boundaries and wait for owner approval.

## Stack and constraints
- Python 3.11.9 and pandas 3.0.2 (reported; Claude's sandbox mirrors them)
- SQLite via stdlib sqlite3; SQL kept PostgreSQL-compatible where practical
- Power BI Desktop (Windows); the owner builds the .pbix
- Use pathlib, no absolute paths, run scripts from the repo root
- Never commit raw CSVs, processed data or database files. Never fabricate data.

## Architecture
    data/raw CSVs -> profile_data -> extract -> transform -> validate -> load -> reconcile
    -> data/processed/olist_staging.sqlite                                    (stage: etl)
    -> sql/schema.sql + sql/load_star.sql -> reconcile_star (33 checks)
    -> data/processed/olist_star.sqlite                                       (stage: model)
    -> sql/analysis/NN_*.sql (read-only) -> docs/analysis/NN_*.csv            (stage: analyze)
    -> Power BI exports/DAX/dashboard
    -> frontend/data/*.json -> HTML/CSS/JavaScript dashboard
Stages: python run_pipeline.py profile | etl | model | analyze | dashboard. The model stage builds the star
database into a temporary file (olist_star.sqlite.tmp) with the staging database attached
read-only, runs the reconciliation checks, and only then atomically replaces olist_star.sqlite. A
failed build leaves the previous star database untouched and removes the temporary file. The
analyze stage opens the star database read-only, runs every sql/analysis/NN_*.sql file, and
writes one CSV per query only after all queries succeed (a failing query leaves existing CSVs
untouched).

## Star schema (Phase 3)
Owner-approved design. DDL in sql/schema.sql, load in sql/load_star.sql, ER diagram and column
lists in docs/star_schema.md.
- Dimensions: dim_date (1,096 days, 2016-01-01 to 2018-12-31), dim_customer (grain = customer_id,
  99,441 rows; customer_unique_id kept: 96,096 people, 2,997 repeat buyers), dim_product (32,951,
  with English category), dim_seller (3,095).
- Facts: fact_orders (order grain, 99,441; holds the order-grain measures payment_total and
  review_score), fact_order_items (112,650), fact_order_payments (103,886).
- Rules: surrogate integer keys with foreign keys declared (SQLite enforces them only with
  PRAGMA foreign_keys = ON); all orders are kept (775 have no items); is_delivered flag on facts;
  revenue = SUM(price) on delivered orders (freight reported separately); latitude/longitude are
  NULL where the ZIP has no geolocation row (279 customers, 7 sellers); review comment text is not
  in the model; money is REAL, so compare with ROUND(x, 2).
- Never sum order-grain measures (payment_total, review_score) across fact_order_items rows; use
  fact_orders for them. Use COUNT(DISTINCT customer_unique_id) to count people.

## Analysis (Phase 4)
Ten queries in sql/analysis/NN_name.sql, run by `python run_pipeline.py analyze`. Each file's
header states its business question, definitions, window and grain. Results are in
docs/analysis/NN_name.csv (UTF-8, LF line endings, empty cell = NULL).
- Queries: 01 monthly revenue, orders and growth; 02 January-August year-over-year growth;
  03 category performance (Pareto); 04 freight burden by category; 05 delivery delay versus review
  score; 06 repeat-buyer share; 07 cohort retention (30/90/180 days); 08 state delivery
  performance; 09 seller delivery performance; 10 payment mix.
- Conventions: delivered orders only (is_delivered = 1); revenue = sum of item price, with freight
  reported separately. Trend window = full months 2017-01 to 2018-08 (2016-09, 2016-10 and 2016-12
  are launch months with 4, 324 and 1 orders, 2016-11 has no orders, and 2018-09 and 2018-10 have 16
  and 4 orders). The data has no cost data, so freight as a percentage of price is a proxy and is
  never called margin. Ranking thresholds: categories need 100 delivered items, states 300
  delivered orders, sellers 30 delivered orders; smaller groups are listed with a NULL rank. A
  person is a customer_unique_id. An order with several sellers counts toward each seller (each
  seller once per order). Cohort retention counts only people with enough follow-up time and does
  not count extra orders placed within 24 hours of the first as returns.
- Rounding: ROUND follows SQLite, which rounds the binary floating-point value, so an exact tie
  can round down. The "1-7 days late" average review score in query 05 is exactly 2.715 and shows
  as 2.71 (half-up rounding would show 2.72).
- Data note (Claude sandbox figures): payments exceed item price plus freight by only 2,688 BRL
  (0.017%) on delivered orders and by 39 BRL on non-delivered orders with items. The overall excess
  of about 165,319 BRL is 98% payments (162,592 BRL) recorded on the 775 orders that have no items
  (603 unavailable, 164 canceled, 8 other statuses).

## Repository structure (current)
    data/raw/                 local Kaggle CSVs (gitignored)
    data/processed/           cleaned CSVs, olist_staging.sqlite, olist_star.sqlite (gitignored)
    etl/__init__.py, profile_data.py, extract.py, transform.py, validate.py, reconcile.py,
        load.py, model.py, reconcile_star.py, analyze.py, dashboard.py
    frontend/index.html, frontend/css/styles.css, frontend/js/app.js, frontend/data/*.json
    sql/schema.sql, sql/load_star.sql, sql/analysis/01_*.sql ... 10_*.sql
    docs/data_quality_report.md, docs/star_schema.md, docs/README.md, docs/analysis/01_*.csv ... 10_*.csv
    run_pipeline.py, requirements.txt, .gitignore, CLAUDE.md
Planned: powerbi/, root README.md

## Roadmap and status
| Phase | Scope | Status |
| 1 | Intake, profiling, data-quality report | Verified |
| 2 | Modular ETL (extract, transform, validate, reconcile, load) | Verified |
| 3 | SQLite star schema + reconciliation | Verified |
| 4 | 10 SQL analysis queries | Verified |
| 5 | Power BI handoff (semantic model, DAX, validation, report pages) | Semantic model verified; report pages pending |
| 5A | Interactive HTML/CSS/JavaScript dashboard | Complete and browser-validated |
| 6 | README, findings, Git/GitHub publish | Not started |

## Verified
- Phase 1 profiling matches the independent reference. Raw rows: orders 99,441
  (96,478 delivered); items 112,650; payments 103,886; reviews 99,224; customers 99,441;
  products 32,951; sellers 3,095; geolocation 1,000,163; 0 orphan keys.
- Phase 2 ETL (`python run_pipeline.py etl`) exits 0, passes validation and reconciliation,
  and repeat runs produce identical cleaned-CSV hashes. SQLite staging row counts: orders
  99,441; order_items 112,650; payments 103,886; reviews 98,673; customers 99,441; products
  32,951; sellers 3,095; geolocation 19,011; category_translation 74.
- Validation (etl/validate.py) fails loudly with ValidationError, tested with bad data:
  untranslated product category; null or out-of-bounds geolocation coordinates; review_score
  null or outside 1-5; null key columns; payment_type outside {credit_card, boleto, voucher,
  debit_card, unknown}; price <= 0; negative freight; duplicate keys; orphan keys.
- Staging reconciliation (etl/reconcile.py, run after load) compares expected, cleaned and SQLite
  row counts for all 9 tables and raises ReconciliationError on any mismatch.
- extract.py logs unparseable date values: 0 in all 8 date columns.
- Phase 3: `python run_pipeline.py model` builds olist_star.sqlite. Row counts: dim_date 1,096;
  dim_customer 99,441; dim_product 32,951; dim_seller 3,095; fact_orders 99,441;
  fact_order_items 112,650; fact_order_payments 103,886. PRAGMA foreign_key_check returns no
  rows; PRAGMA integrity_check is ok.
- Star reconciliation (etl/reconcile_star.py, run inside the build before the atomic replace):
  25 count/total/business-rule/foreign-key checks plus 8 row-level fidelity checks that compare
  each table's content with staging through an independent join path (EXCEPT in both directions);
  all 33 pass. Totals: SUM(price) 13,591,643.70; SUM(freight_value) 2,251,909.54;
  SUM(payment_value) 16,008,872.12; delivered revenue 13,221,498.11 over 110,197 item rows;
  delivered orders 96,478; late 6,534, on time 89,936, NULL 2,971; reviewed orders 98,673;
  orders without items 775; orders without payments 1.
- Tested with deliberate corruptions: 20 of 21 are caught, including wrong-row errors (wrong
  product, seller, payment type, review score, date, customer, delay, status). The one uncaught
  corruption, a tampered dim_date value, is a known limitation: dim_date is generated, not loaded
  from staging, and Claude verified all 1,096 rows against Python's calendar.
- A load bug that assigns the wrong seller while counts, totals and foreign keys stay valid fails
  the build; a failed build leaves the previous star file byte-identical and no .tmp file behind.
- The staging database is attached read-only (write attempts fail) and is unchanged by the model
  stage. Two builds give identical table contents, identical to an independent build made in
  Claude's sandbox. Build time is about 40 seconds on the owner's machine (reported).
- Claude independently re-ran the pipeline in a sandbox matching Python 3.11.9 / pandas 3.0.2,
  reproduced Copilot's results, and tested validation, reconciliation and the star build with its
  own bad data.
- Phase 4: `python run_pipeline.py analyze` runs the 10 queries read-only and writes
  docs/analysis/NN_*.csv with row counts 20, 2, 74, 74, 8, 7, 21, 27, 2,970 and 11. Runs are
  deterministic (identical CSV hashes) and leave the star database unchanged. Failure handling is
  tested: missing star database, a broken query, a query with no rows and a comment-only file all
  raise a clear error and write no CSV.
- Claude recomputed every analysis query independently from the raw Kaggle files with pandas (no
  ETL, staging or star involved, using SQLite's rounding rule) and all results match, row order
  included; Claude's own copy of each CSV is byte-identical to the owner's.
- Headline results (all verified): January-August 2018 versus 2017: orders +135.1%, delivered
  revenue +141.1%. Delivered orders that arrived 1+ days late average a 2.27 review score versus
  4.29 for on-time orders (62.4% versus 9.3% 1-2 star reviews; 8+ days late: 1.70). Repeat buyers:
  2,801 of 93,358 buyers (3.0%), 6.14% of delivered orders and 5.51% of revenue; returning within
  30/90/180 days: 0.63% / 1.28% / 1.96% (only people with enough follow-up time; 850 people placed an
  extra order within 24 hours). The top 10 categories earn 62.43% of delivered revenue
  (health_beauty 9.33%). Highest late rates among states with 300+ delivered orders: AL 21.4%, MA
  17.4%, SE 15.2%; SP has 4.5% late and 38.33% of revenue. Credit cards carry 78.46% of payment
  value (74.03% of payments); 2,182 delivered orders (5.19% of payments) used 2+ payment types.
- Phase 5 semantic model: Power BI Desktop model `olist_dashboard.pbix` connected through the
  local Power BI Authoring MCP server. Seven required relationships are present, including the
  inactive delivered-date relationship; no direct date-to-items or cohort relationship exists.
  Five calculated columns and all 38 measures are Ready with no errors. Smoke validation passed
  for delivered orders (96,478), buyers (93,358), repeat buyers (2,801), category ranking and
  Pareto shares. `Revenue MoM %` was corrected to explicitly calculate the prior calendar month;
  it returns blank for 2017-01, 109.5052% for 2017-02, and 53.3574% for 2017-03.
- Phase 5A dashboard: `python run_pipeline.py dashboard` exports all ten read-only analysis
  datasets plus overview metrics to `frontend/data/`. It powers three responsive
  views: Overview; Products & categories; and Customers & delivery. The browser validation
  confirmed all views render their charts and tables, year/category filters and reset work,
  and the verified all-period totals remain 96,478 delivered orders and 13,221,498.11 BRL
  revenue. Generated JSON matches every analysis CSV field-for-field, repeated exports leave
  the star database byte-identical, and missing-database failure handling is explicit.
- Documentation and regression coverage: root README.md now documents setup, architecture,
  dashboard usage, verified findings, and validation. `tests/test_dashboard.py` runs three
  standard-library unittest cases covering all dashboard dataset row counts and headline totals,
  field-for-field parity with every analysis CSV, and clear missing-database failure handling;
  all tests pass.
- Frontend integration verification: regenerated all dashboard JSON from the star database,
  confirmed the overview displays R$13,221,498.11 revenue, 96,478 orders, R$137.04 AOV,
  3% repeat-buyer rate, and 6.8% late rate. Browser checks confirmed 2018 filtering produces
  R$7,218,125.12 and 52,783 orders over 8 trend points, category filtering narrows the table,
  reset restores all defaults, and Overview, Products & categories, and Customers & delivery
  each render the expected charts and populated tables.
- Static dashboard UX improvements: exports validate every dataset's expected columns and write
  `frontend/data/metadata.json` with UTC refresh time, source, static-export flag, row counts,
  and schema. The header displays the refresh time; category, state, and seller tables support
  search, sorting, and row limits; Chart.js is vendored locally for offline use. Browser checks
  confirmed the new controls filter and limit rows correctly, while the dashboard regression
  suite remains green.
- Table row-limit fix: state and seller controls now default to 10 rows in both HTML and
  JavaScript, synchronize their visible selection during rendering, and render all rows inside
  fixed-height independently scrollable table containers. Browser checks confirmed 10 -> All ->
  10 transitions, 21 state rows and 627 seller rows on All, with no page-layout expansion.
- Filter header polish: centered the "Explore the data" heading block vertically in its
  container and slightly increased its heading and scope-note sizes for better visual balance.
- Frontend spacing fix: dashboard pages now use a shared 16px grid gap between every major
  section, including KPI rows and the chart/table sections, across all three views. Browser
  measurement confirmed a 16px gap on Overview, Products & categories, and Customers & delivery.

## Cleaning rules (approved by the owner; geolocation rule amended and approved)
- Geolocation: drop raw rows outside lat -34..6 / lng -74..-32 (the east bound keeps
  Fernando de Noronha, ZIP 53990); then one row per ZIP prefix with median lat/lng and
  the most frequent (city, state) pair (ties alphabetical). Bounds are constants in
  etl/transform.py, imported by etl/validate.py. 31 raw rows dropped; 4 ZIP prefixes are
  absent because every raw row had impossible coordinates: 18243, 78131, 83252, 95130.
  Join to geolocation with LEFT JOIN: 279 customers and 7 sellers have no geolocation
  row. Customers and sellers carry their own city/state.
- Reviews: keep the latest review per order (creation date, answer timestamp, then
  review_id): 99,224 -> 98,673. review_id is NOT unique after cleaning (572 repeats);
  the key is order_id.
- Orders: all statuses kept. delivery_date_inconsistent flags delivered orders without a
  delivery date and non-delivered orders with one. delivery_delay_days = whole days from
  the estimated date (stored at midnight) to delivery; 0 = delivered on the estimated
  date; computed only for consistent delivered orders (96,470). is_late = delay > 0:
  6,534 true, 89,936 false, 2,971 null. Non-delivered orders are excluded from revenue
  and delay metrics at analysis time, not removed in the ETL.
- Products: missing category -> "unknown" (610 products); columns product_name_length and
  product_description_length renamed from the source misspellings.
- Category translations: 71 source rows + pc_gamer -> pc_gamer +
  portateis_cozinha_e_preparadores_de_alimentos -> portable_kitchen_and_food_preparers +
  unknown -> unknown = 74 rows.
- Payments: payment_type not_defined -> unknown (3 rows); payment_value_non_positive
  flags 9 rows.
- Identify repeat customers by customer_unique_id, not customer_id.

## Pending next steps
1. Phase 5 (design with the owner first): Power BI handoff: CSV exports from the star database
   (dimensions and facts), DAX measures, a 3-page build guide (executive overview; product and
   category performance; customer and delivery insights). The owner builds the .pbix in Power BI
   Desktop (Windows) later, using the same definitions and star database.
2. Phase 6: publish the completed README, findings, and dashboard documentation on GitHub after
   the owner initializes Git. The Mermaid ER diagram is present in docs/star_schema.md.
3. Optional future work: expand automated tests beyond the dashboard export regression suite to
   cover ETL, reconciliation, and analysis failure paths.
4. Initialize Git (postponed by owner), then push to GitHub. data/ is gitignored; the small
   docs/analysis CSVs and frontend assets can be committed.

## Commands (repo root, Windows PowerShell)
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    python run_pipeline.py profile
    python run_pipeline.py etl
    python run_pipeline.py model
    python run_pipeline.py analyze
    python run_pipeline.py dashboard
Run the stages in the order etl, model, analyze: model reads data/processed/olist_staging.sqlite
and analyze reads data/processed/olist_star.sqlite.
Dataset: Kaggle "Brazilian E-Commerce Public Dataset by Olist"; put the nine CSVs in
data/raw/.

## Known issues
- No automated test suite; the pipeline's own checks were negative-tested ad hoc.
- Money is stored as REAL; compare with ROUND(x, 2). ROUND of an exact tie can round down (see the
  Rounding note in the Analysis section).
- The star checks prove the star faithfully reflects staging; correctness of the cleaning rules
  themselves is covered by the Phase 1-2 checks.
- dim_date is generated and not compared with staging (verified separately against Python's
  calendar).
- shipping_limit_date contains values up to 2020-04-09 (a source data quirk); it is a plain
  column and not a date key.
- ZIP prefixes are read as integers (leading zeros dropped; consistent across tables).
- The analyze stage does not delete the CSV of a query file that was removed or renamed; delete it
  by hand.
- Git not initialized.

## Guidance for the next agent
Read this file first. Do not redo verified work. Do not mark items verified without
evidence. Pause for owner confirmation at phase boundaries and before architecture
changes. Update this file only on meaningful state changes, with complete contents.