# Dashboard validation checklist

Every number below comes from the verified SQL analysis (`docs/analysis/*.csv`) or from an independent
recomputation from the raw Kaggle files. Build a hidden page called **Validation** in Power BI with
the cards and tables described here, work through the checks in order, and tick each one.

Rules: clear all slicers and filters unless a check says otherwise. Money must match to the cent,
percentages to the decimals shown. Fix the first mismatch before looking at later ones, because
later checks often depend on earlier ones.

If a value does not match, send the check ID, the value Power BI shows, the expected value and a
screenshot of the visual, and we will debug it together. The usual causes are in BUILD_GUIDE.md,
section 9.

## V01. Totals (cards, no filters)

| Measure | Expected |
|---|---|
| Orders Placed | 99,441 |
| Delivered Orders | 96,478 |
| Delivered Revenue | 13,221,498.11 |
| Delivered Freight | 2,198,275.64 |
| Avg Order Value | 137.04 |
| Orders With Delay | 96,470 |
| Late Orders | 6,534 |
| Late Rate % | 6.8% (6.77% with 2 decimals) |
| Avg Delay Days | -11.9 (-11.88) |
| Reviewed Orders | 95,832 |
| Avg Review Score | 4.16 |
| Low Review Share % | 12.8% (12.81%) |
| Five Star Share % | 59.2% (59.22%) |
| Buyers | 93,358 |
| Repeat Buyers | 2,801 |
| Repeat Rate % | 3.00% |
| Items Sold | 110,197 |
| Item Revenue | 13,221,498.11 |
| Item Freight | 2,198,275.64 |
| Freight % of Price | 16.6% (16.63%) |
| Payments Count | 100,756 |
| Payment Value | 15,422,461.77 |
| Avg Payment Value | 153.07 |
| Orders Paid With 2+ Payment Types | 2,182 |

Source: raw Kaggle files, recomputed independently; Delivered Revenue, Item Revenue, Late Orders,
Repeat Buyers and the payment figures also appear in the SQL results (queries 01, 03, 05, 06, 10).
Note: Delivered Revenue (order grain) and Item Revenue (item grain) must be identical.

## V02. Monthly trend (table: dim_date[year_month] with a visual filter 2017-01 to 2018-08)

Columns: [Orders Placed], [Delivered Orders], [Delivered Revenue], [Delivered Freight],
[Avg Order Value], [Revenue MoM %]. The 20 rows must equal `docs/analysis/01_monthly_revenue_orders.csv`.
Spot checks:

| Month | Orders placed | Delivered orders | Delivered revenue | Freight | Avg order value | MoM growth |
|---|---|---|---|---|---|---|
| 2017-01 | 800 | 750 | 111,798.36 | 15,684.01 | 149.06 | blank |
| 2017-02 | 1,780 | 1,653 | 234,223.40 | 37,015.92 | 141.70 | 109.5% |
| 2017-11 | 7,544 | 7,289 | 987,765.37 | 165,598.83 | 135.51 | 52.4% |
| 2018-03 | 7,211 | 7,003 | 953,356.25 | 167,241.99 | 136.14 | 15.4% |
| 2018-08 | 6,512 | 6,351 | 838,576.64 | 146,915.00 | 132.04 | -3.4% |

2017-01 must show a blank growth (it is the first month of the trend window).

## V03. Year over year (card visuals; set the date slicer to 2018-01-01 .. 2018-08-31)

| Measure | Expected |
|---|---|
| Delivered Revenue | 7,218,125.12 |
| Revenue Same Period LY | 2,993,456.13 |
| Revenue YoY % | 141.1% |
| Orders Placed | 53,991 |
| Orders Same Period LY | 22,968 |
| Orders YoY % | 135.1% |

Source: query 02. Clear the slicer afterwards.

## V04. Revenue by delivery month (table: dim_date[year_month], visual filter 2017-01 to 2018-08)

| Month | Delivered Revenue (by purchase month) | Revenue by Delivery Month |
|---|---|---|
| 2017-11 | 987,765.37 | 651,457.52 |
| 2018-03 | 953,356.25 | 892,100.11 |
| 2018-08 | 838,576.64 | 1,141,791.54 |

Source: raw Kaggle files (delivered date month vs purchase month). The two columns differ because
an order is placed in one month and arrives later. 8 delivered orders (1,249.18 of revenue) have no
delivery date; they appear only in a (Blank) row if the table is not filtered.

## V05. Categories (table: dim_product[category_name_english]; clear all filters)

The full table must equal `docs/analysis/03_category_performance.csv` (74 rows) and, for the freight
columns, `04_category_freight_burden.csv`. Spot checks:

| Category | Items sold | Item revenue | Revenue share % | Revenue rank | Cumulative share % |
|---|---|---|---|---|---|
| health_beauty | 9,465 | 1,233,131.72 | 9.33% | 1 | 9.33% |
| watches_gifts | 5,859 | 1,166,176.98 | 8.82% | 2 | 18.15% |
| bed_bath_table | 10,953 | 1,023,434.76 | 7.74% | 3 | 25.89% |
| toys | 4,030 | 471,286.48 | 3.56% | 10 | 62.43% |

| Category | Items sold | Freight % of Price | Freight % of Price Min 100 Items |
|---|---|---|---|
| christmas_supplies | 150 | 36.5% | 36.5% (rank 1 among categories with 100+ items) |
| home_comfort_2 | 30 | 54.0% | blank (fewer than 100 items) |

## V06. States (table: dim_customer[state]; clear all filters)

The table must equal `docs/analysis/08_state_delivery_performance.csv` (27 rows). Spot checks:

| State | Delivered Orders | Late Orders | Late Rate % | Late Rate % Min 300 Orders | Avg Review Score |
|---|---|---|---|---|---|
| AL | 397 | 85 | 21.4% | 21.4% | 3.85 |
| SP | 40,501 | 1,820 | 4.5% | 4.5% | 4.25 |
| AM | 145 | 4 | 2.8% | blank (fewer than 300 orders) | 4.24 |

## V07. Delay buckets (table: fact_orders[delay_bucket], filter: not blank)

Columns: [Reviewed Orders], [Avg Review Score], [Low Review Share %], [Five Star Share %]. Must equal
`docs/analysis/05_delay_vs_review.csv` rows 1 to 5:

| Bucket | Reviewed orders | Avg review score | Low review share | Five star share |
|---|---|---|---|---|
| 10+ days early | 61,523 | 4.32 | 8.9% | 64.0% |
| 1-9 days early | 26,640 | 4.23 | 10.0% | 58.9% |
| on the estimated date | 1,280 | 4.03 | 12.4% | 50.6% |
| 1-7 days late | 3,600 | 2.71 | 49.4% | 23.9% |
| 8+ days late | 2,781 | 1.70 | 79.3% | 7.0% |

The exact average of the '1-7 days late' bucket is 2.715, so Power BI may display 2.71 or 2.72; both
are correct (the SQL shows 2.71 because SQLite rounds the binary value).

## V08. Payments by type (table: fact_order_payments[payment_type]; clear all filters)

| Type | Payments Count | Payments Share % | Payment Value | Payment Value Share % |
|---|---|---|---|---|
| credit_card | 74,586 | 74.03% | 12,101,094.88 | 78.46% |
| boleto | 19,191 | 19.05% | 2,769,932.58 | 17.96% |
| voucher | 5,493 | 5.45% | 343,013.19 | 2.22% |
| debit_card | 1,486 | 1.47% | 208,421.12 | 1.35% |

Source: query 10. There is no row for payment type 'unknown' because no delivered order uses it.

## V09. Credit card installments (table: fact_order_payments[installment_group], filter payment_type = credit_card)

| Group | Payments Count | Payments Share % | Payment Value Share % |
|---|---|---|---|
| 1 installment (or none) | 24,761 | 24.58% | 15.35% |
| 2-3 installments | 22,239 | 22.07% | 19.27% |
| 4-6 installments | 15,790 | 15.67% | 18.48% |
| 7-10 installments | 11,467 | 11.38% | 24.60% |
| 11+ installments | 329 | 0.33% | 0.77% |

Shares are of ALL delivered payments, not of credit card payments only.

## V10. Repeat buyers and return rates

| Item | Expected |
|---|---|
| [Buyers] | 93,358 |
| [Repeat Buyers] | 2,801 |
| [Repeat Rate %] | 3.00% |
| return_rate_30d_pct (cohort_month = ALL COHORTS, Maximum) | 0.63 |
| return_rate_90d_pct | 1.28 |
| return_rate_180d_pct | 1.96 |

The return rates come straight from the verified SQL query 07 (imported as a table); they are not
recomputed in DAX.

## V11. A filter test (proves the grain logic)

Select state SP in a slicer. Expected: [Delivered Orders] = 40,501 and [Late Rate %] = 4.5%. Then
select the category health_beauty as well: [Item Revenue] must drop below 13,221,498.11 and
[Delivered Orders] must NOT change when you change the category (category filters reach only the
item table). If [Delivered Orders] changes with the category, a relationship direction is wrong.

## Sign-off

When V01 to V11 all pass, the dashboard agrees with the verified SQL analysis. Record the date and
your Power BI Desktop version here, and tell Claude, so `CLAUDE.md` can be updated.
