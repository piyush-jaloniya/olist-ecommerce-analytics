# Olist dashboard: Power BI build guide

This guide turns the exported star schema into a three-page dashboard. Everything the
dashboard shows must agree with the verified SQL analysis; `VALIDATION.md` lists the numbers
to check. Estimated time: 3 to 4 hours the first time.

## 0. Before you start

- Power BI Desktop (free, Windows). Check the version under File > Account, and note it in
  your README.
- The data must be fresh. From the repository root, with the virtual environment active:

      python run_pipeline.py etl
      python run_pipeline.py model
      python run_pipeline.py analyze
      python run_pipeline.py export

  `export` writes 7 CSV files to `data/processed/powerbi/` (about 50 MB, not committed to Git).
- Turn off automatic date tables: File > Options and settings > Options > Current File >
  Data Load > untick **Time intelligence: Auto date/time**. Otherwise Power BI creates hidden
  date tables that confuse the date logic.
- Set the file locale: File > Options > Current File > Regional Settings > **English (United
  States)**, so that "." is read as the decimal separator.

## 1. Import the data

Home > Get data > Text/CSV, then load each of these files from `data/processed/powerbi/`.
In the preview click **Transform Data** (not Load) so you can set the column types in Power
Query. Use File origin **65001: Unicode (UTF-8)**.

Set these column types (select the column, Transform > Data Type). Columns not listed stay
as Text or as detected.

| Table | Whole number | Date | Date/Time | Decimal (use **Fixed decimal number** for money) | Text |
|---|---|---|---|---|---|
| dim_date | date_key, year, quarter, month, day_of_month, day_of_week, is_weekend | full_date | | | month_name, year_month, day_name |
| dim_customer | customer_key | | | latitude, longitude (Decimal number) | customer_id, customer_unique_id, zip_code_prefix, city, state |
| dim_product | product_key, name_length, description_length, photos_qty | | | weight_g, length_cm, height_cm, width_cm (Decimal number) | product_id, category_name, category_name_english |
| dim_seller | seller_key | | | latitude, longitude (Decimal number) | seller_id, zip_code_prefix, city, state |
| fact_orders | order_key, customer_key, is_delivered, purchase_date_key, approved_date_key, carrier_date_key, delivered_date_key, estimated_delivery_date_key, review_creation_date_key, delivery_date_inconsistent, delivery_delay_days, is_late, item_count, payment_count, review_score | | purchase_timestamp, approved_timestamp, carrier_timestamp, delivered_timestamp | items_price_total, items_freight_total, payment_total (Fixed decimal number) | order_id, order_status |
| fact_order_items | order_item_key, order_key, order_item_id, product_key, seller_key, purchase_date_key, is_delivered | | shipping_limit_timestamp | price, freight_value (Fixed decimal number) | |
| fact_order_payments | order_payment_key, order_key, payment_sequential, payment_installments, payment_value_non_positive | | | payment_value (Fixed decimal number) | payment_type |

Why Fixed decimal number for money: it stores exactly 4 decimals, so sums of prices match the
SQL results to the cent. Click **Close & Apply**.

Also import the cohort result (a small pre-aggregated table used for the return-rate cards):
Get data > Text/CSV > `docs/analysis/07_cohort_retention.csv`. Types: `cohort_month` Text; all
other columns Whole number, except the three `return_rate_*_pct` columns, which are Decimal.

## 2. Model (Model view)

Delete any relationship Power BI created automatically that is not in this list, then create
these (drag the key from the "one" side to the "many" side; all single direction, one to many):

| From (one) | To (many) | Active |
|---|---|---|
| dim_date[date_key] | fact_orders[purchase_date_key] | **Yes** |
| dim_date[date_key] | fact_orders[delivered_date_key] | **No (inactive)** |
| dim_customer[customer_key] | fact_orders[customer_key] | Yes |
| fact_orders[order_key] | fact_order_items[order_key] | Yes |
| fact_orders[order_key] | fact_order_payments[order_key] | Yes |
| dim_product[product_key] | fact_order_items[product_key] | Yes |
| dim_seller[seller_key] | fact_order_items[seller_key] | Yes |

Notes:
- Do NOT relate dim_date to fact_order_items. Power BI allows only one active path between two
  tables, and dates already reach the items through fact_orders. (fact_order_items still has a
  purchase_date_key column; just do not use it for a relationship.)
- Do NOT relate the imported 07_cohort_retention table to anything.
- The inactive delivered-date relationship is used by one measure (Revenue by Delivery Month)
  through USERELATIONSHIP.
- dim_seller is not used by any page. It stays in the model for completeness.

What this means for measures (this is the idea to explain in an interview): a filter flows
from a dimension to the facts below it, never upward. A filter on dim_product (category)
reaches only fact_order_items, so every measure sliced by category is defined on the item
table. A filter on dim_customer (state) or on dates reaches fact_orders and, through it, the
items and payments. That is why revenue by category and late rate by state are separate
measures at different grains.

Then:
1. dim_date: Table tools > **Mark as date table** > choose full_date.
2. Hide the key columns in report view (right-click > Hide in report view): every column
   ending in `_key`, plus order_id, customer_id, product_id, seller_id.
3. For every numeric column, set Summarize by to **None** (Column tools), except where you
   plan to drag it directly. The measures do all the aggregation.

## 3. Calculated columns and measures

1. Create the measures table: Home > Enter data > leave it empty, name it `_Measures`, Load.
   (A dedicated table keeps the field list tidy.)
2. Open `measures.dax`. Create the 5 calculated columns of PART 1 (select the table, Table
   tools > New column, paste the definition).
3. In the model, set **Sort by column**: delay_bucket sorted by delay_bucket_order;
   installment_group sorted by installment_group_order. Hide both order columns.
4. Create the measures of PART 2 (select `_Measures`, Home > New measure, paste each
   definition). Set the format given in the comment above each (for example "percentage, 1
   decimal"). You can also paste several at a time in the DAX query view and use "Update model".
5. If a formula shows a red underline, read the message: the usual causes are a column name
   typo or a column imported with the wrong type (see section 1).

Quick test: add a card with [Delivered Orders]. It must show 96,478. If it shows 99,441 the
filter on is_delivered was not applied: check the column is a whole number.

## 4. Page 1: Executive overview

Purpose: the business at a glance, and the trend.

    +----------------------------------------------------------------------+
    | Olist marketplace: executive overview                 [date slicer]  |
    +----------+----------+----------+----------+----------+---------------+
    | Delivered| Delivered| Avg order| Late     | Avg      | Repeat buyer  |
    | revenue  | orders   | value    | rate %   | review   | rate %        |
    +----------+----------+----------+----------+----------+---------------+
    |  Monthly delivered revenue (columns) + orders placed (line)          |
    |                                                                      |
    +-------------------------------------+--------------------------------+
    |  Revenue MoM % by month (table)     |  Revenue: placed vs delivered  |
    |                                     |  month (line chart)            |
    +-------------------------------------+--------------------------------+

- **Date slicer**: field dim_date[full_date], slicer type Between. Default to 2017-01-01 -
  2018-08-31 (the trend window: earlier months are launch months with 4, 324 and 1 orders,
  2016-11 has no orders, and 2018-09/10 have 16 and 4 orders).
- **Cards** (six): [Delivered Revenue], [Delivered Orders], [Avg Order Value], [Late Rate %],
  [Avg Review Score], [Repeat Rate %].
- **Combo chart** (Line and clustered column): X axis dim_date[year_month]; columns
  [Delivered Revenue]; line [Orders Placed] on the secondary axis.
- **Table**: dim_date[year_month], [Delivered Revenue], [Revenue MoM %], [Revenue YoY %].
- **Line chart**: X axis dim_date[year_month]; values [Delivered Revenue] and
  [Revenue by Delivery Month]. The gap between the two lines is the delivery lag.
- Add a text box under the title with the definition: "Revenue = item price of delivered
  orders, freight excluded."

## 5. Page 2: Products and categories

Purpose: which categories drive revenue, and which carry high freight cost.

    +----------------------------------------------------------------------+
    | Products and categories                                [date slicer] |
    +---------------------------------+------------------------------------+
    |  Top 10 categories by revenue   |  Pareto: revenue (columns) and     |
    |  (bar chart)                    |  cumulative share % (line)         |
    +---------------------------------+------------------------------------+
    |  Freight % of price, categories |  Category table                    |
    |  with 100+ items (bar chart)    |                                    |
    +---------------------------------+------------------------------------+

- **Bar chart**: Y axis dim_product[category_name_english]; X axis [Item Revenue]. Visual
  filter: Top N = 10 by [Item Revenue].
- **Pareto**: X axis dim_product[category_name_english], sorted by [Item Revenue] descending;
  columns [Item Revenue]; line [Cumulative Revenue Share %] on the secondary axis. Visual
  filter: Top N = 20 by [Item Revenue]. Keep one category per row.
- **Freight bar chart**: Y axis dim_product[category_name_english]; X axis
  [Freight % of Price Min 100 Items]. Visual filter: [Freight % of Price Min 100 Items] is not
  blank; Top N = 10 by that measure. Add a note: "freight as % of price; the data has no
  product cost, so this is not a margin".
- **Table**: category, [Items Sold], [Item Revenue], [Revenue Share %], [Revenue Rank],
  [Freight % of Price].
- Set the date slicer to Between 2017-01-01 and 2018-08-31 only if you want the trend window;
  the SQL results in VALIDATION.md use ALL dates (leave the slicer cleared when you validate).

## 6. Page 3: Customers and delivery

Purpose: delivery performance drives reviews, most buyers never return, and the payment mix.

    +----------------------------------------------------------------------+
    | Customers and delivery                                               |
    +----------------------+----------------------+------------------------+
    | Repeat buyers (card) | Repeat rate (card)   | Returned within 30 /   |
    |                      |                      | 90 / 180 days (cards)  |
    +----------------------+----------------------+------------------------+
    | Review score by delay bucket                | Late rate % by state    |
    | (columns) + low-review share (line)         | (300+ orders, bar)      |
    +---------------------------------------------+-------------------------+
    | Payment value share by type (bar)           | Credit card installments|
    |                                             | (columns)               |
    +---------------------------------------------+-------------------------+

- **Cards**: [Repeat Buyers], [Repeat Rate %], [Orders Paid With 2+ Payment Types].
- **Return-rate cards** (from the imported `07_cohort_retention` table): three cards showing
  return_rate_30d_pct, return_rate_90d_pct and return_rate_180d_pct, aggregation **Maximum**,
  each with the visual filter cohort_month = "ALL COHORTS". Format as 0.00 and add a "%"
  suffix in the title. Add a note: "only people with enough follow-up time; orders within 24
  hours of the first do not count as returns".
- **Delay chart**: X axis fact_orders[delay_bucket]; columns [Avg Review Score]; line
  [Low Review Share %] on the secondary axis. Visual filter: delay_bucket is not blank.
- **State bar chart**: Y axis dim_customer[state]; X axis [Late Rate % Min 300 Orders]. Visual
  filter: the measure is not blank; Top N = 10 by the measure.
- **Payment bar chart**: Y axis fact_order_payments[payment_type]; X axis
  [Payment Value Share %].
- **Installments chart**: X axis fact_order_payments[installment_group]; columns
  [Payments Share %]. Visual filter: payment_type = credit_card.

## 7. Validate against the SQL results

Open `VALIDATION.md` and work through every check. Do this before you style anything. A
mismatch is a bug in the model, a column type, a relationship or a measure, and it is much
easier to find now.

## 8. Style, save and publish

- Use one theme (View > Themes), consistent number formats, and a title on every visual.
- Keep every page to its single question; avoid more than 6 to 8 visuals per page.
- Save the report as `olist_dashboard.pbix` in this folder. **Do not commit the .pbix**: it
  embeds all the data (tens of MB). Commit screenshots instead: File > Export > PDF, and
  screenshots of each page into `powerbi/screenshots/` (PNG).
- For your README: a screenshot of each page, the list of the 10 SQL analyses, and one
  sentence on each insight.

## 9. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| A measure by category shows the same value on every row | The measure reads fact_orders. Category filters reach only fact_order_items; use the item measures (section D of measures.dax) |
| "A circular dependency" or an ambiguity error on a relationship | Two active paths between two tables. Keep only the relationships in section 2 |
| Revenue differs by a few cents | The money columns were imported as Decimal number instead of Fixed decimal number |
| Dates show as text, or time intelligence measures return blank | dim_date[full_date] is not a Date type, or the table is not marked as a date table |
| Counts are wrong for orders without a review or delay | A column was imported as Text; set whole-number types in section 1 |
| A "(Blank)" row appears next to a month table | Orders without a delivery date (8 orders, 1,249.18 of revenue) show under Revenue by Delivery Month; filter the table to the months of interest |
| [Repeat Buyers] is slow | Normal: it iterates 93,000 people. It should finish in seconds; do not put it in a table with thousands of rows |
