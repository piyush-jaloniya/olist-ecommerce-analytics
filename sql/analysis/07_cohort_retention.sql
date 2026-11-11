-- Query 07: cohort retention, return within 30, 90 and 180 days.
-- Business question: what share of customers buy more than once, and how soon?
-- Definitions: a person is a customer_unique_id; only delivered orders count. The cohort is the
--   month of the person's first delivered order (cohorts 2017-01 to 2018-08 only). A person
--   "returned within N days" if they placed another delivered order at least 1 day and at most N
--   days after their first order. Extra orders placed within 24 hours of the first (including at
--   the very same second) are NOT counted as returns; same_day_order_people counts people who
--   placed at least one (likely a split purchase).
--   Right-censoring guard: for each window, only people whose first order is at least N days
--   before the end of the data (the latest delivered purchase) are counted in eligible_Nd, because
--   later buyers have not had time to return. Return rates divide by the eligible people, not by
--   the cohort size; they are NULL when nobody in the cohort is eligible.
--   The last row, ALL COHORTS, pools every cohort.
-- Window: cohorts 2017-01 to 2018-08.
-- Grain: one row per cohort month plus one pooled row. Source: fact_orders joined to dim_customer.
WITH delivered AS (
    SELECT dc.customer_unique_id AS person,
           fo.purchase_timestamp AS ts,
           julianday(fo.purchase_timestamp) AS t
    FROM fact_orders AS fo
    JOIN dim_customer AS dc ON dc.customer_key = fo.customer_key
    WHERE fo.is_delivered = 1
),
firsts AS (
    SELECT person, MIN(t) AS t_first, MIN(ts) AS ts_first
    FROM delivered
    GROUP BY person
),
data_end AS (
    SELECT MAX(t) AS t_end FROM delivered
),
returns AS (
    SELECT d.person, MIN(d.t) AS t_return
    FROM delivered AS d
    JOIN firsts AS f ON f.person = d.person AND d.t >= f.t_first + 1
    GROUP BY d.person
),
same_day AS (
    SELECT d.person
    FROM delivered AS d
    JOIN firsts AS f ON f.person = d.person AND d.t >= f.t_first AND d.t < f.t_first + 1
    GROUP BY d.person
    HAVING COUNT(*) >= 2
),
people AS (
    SELECT SUBSTR(f.ts_first, 1, 7) AS cohort_month,
           f.t_first,
           r.t_return - f.t_first AS days_to_return,
           CASE WHEN s.person IS NOT NULL THEN 1 ELSE 0 END AS same_day_order,
           e.t_end
    FROM firsts AS f
    CROSS JOIN data_end AS e
    LEFT JOIN returns AS r ON r.person = f.person
    LEFT JOIN same_day AS s ON s.person = f.person
    WHERE SUBSTR(f.ts_first, 1, 7) BETWEEN '2017-01' AND '2018-08'
),
cohort_rows AS (
    SELECT cohort_month,
           COUNT(*) AS people,
           SUM(same_day_order) AS same_day_order_people,
           SUM(t_first + 30 <= t_end) AS eligible_30d,
           COALESCE(SUM(t_first + 30 <= t_end AND days_to_return <= 30), 0) AS returned_30d,
           SUM(t_first + 90 <= t_end) AS eligible_90d,
           COALESCE(SUM(t_first + 90 <= t_end AND days_to_return <= 90), 0) AS returned_90d,
           SUM(t_first + 180 <= t_end) AS eligible_180d,
           COALESCE(SUM(t_first + 180 <= t_end AND days_to_return <= 180), 0) AS returned_180d
    FROM people
    GROUP BY cohort_month
    UNION ALL
    SELECT 'ALL COHORTS',
           COUNT(*),
           SUM(same_day_order),
           SUM(t_first + 30 <= t_end),
           COALESCE(SUM(t_first + 30 <= t_end AND days_to_return <= 30), 0),
           SUM(t_first + 90 <= t_end),
           COALESCE(SUM(t_first + 90 <= t_end AND days_to_return <= 90), 0),
           SUM(t_first + 180 <= t_end),
           COALESCE(SUM(t_first + 180 <= t_end AND days_to_return <= 180), 0)
    FROM people
)
SELECT cohort_month,
       people,
       same_day_order_people,
       eligible_30d,
       returned_30d,
       ROUND(100.0 * returned_30d / NULLIF(eligible_30d, 0), 2) AS return_rate_30d_pct,
       eligible_90d,
       returned_90d,
       ROUND(100.0 * returned_90d / NULLIF(eligible_90d, 0), 2) AS return_rate_90d_pct,
       eligible_180d,
       returned_180d,
       ROUND(100.0 * returned_180d / NULLIF(eligible_180d, 0), 2) AS return_rate_180d_pct
FROM cohort_rows
ORDER BY CASE WHEN cohort_month = 'ALL COHORTS' THEN 1 ELSE 0 END, cohort_month;
