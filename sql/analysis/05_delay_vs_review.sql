-- Query 05: delivery delay versus customer review score.
-- Business question: how do delivery delays affect customer reviews?
-- Definitions: delivered orders that have a review and a valid delay. delivery_delay_days = whole
--   days from the estimated delivery date to the actual delivery (0 = delivered on the estimated
--   date, negative = early, positive = late). pct_low_reviews = share of 1-2 star reviews.
--   pct_five_star = share of 5 star reviews. Rows 1-5 are delay buckets; rows 6-8 are summaries
--   that overlap with them (late, not late, all) and must not be added to the buckets.
-- Window: all delivered orders (2016-2018).
-- Grain: one row per delay bucket or summary. Source: fact_orders (order grain, so each order
--   counts once).
WITH base AS (
    SELECT delivery_delay_days AS delay, review_score AS score
    FROM fact_orders
    WHERE is_delivered = 1
      AND delivery_delay_days IS NOT NULL
      AND review_score IS NOT NULL
),
bucketed AS (
    SELECT delay,
           score,
           CASE WHEN delay <= -10 THEN 1
                WHEN delay < 0 THEN 2
                WHEN delay = 0 THEN 3
                WHEN delay <= 7 THEN 4
                ELSE 5 END AS bucket_order
    FROM base
),
combined AS (
    SELECT bucket_order,
           CASE bucket_order WHEN 1 THEN '10+ days early'
                             WHEN 2 THEN '1-9 days early'
                             WHEN 3 THEN 'on the estimated date'
                             WHEN 4 THEN '1-7 days late'
                             ELSE '8+ days late' END AS delay_bucket,
           delay,
           score
    FROM bucketed
    UNION ALL
    SELECT 6, 'SUMMARY: late (1+ days)', delay, score FROM base WHERE delay > 0
    UNION ALL
    SELECT 7, 'SUMMARY: not late (0 days or earlier)', delay, score FROM base WHERE delay <= 0
    UNION ALL
    SELECT 8, 'SUMMARY: all delivered orders with a review', delay, score FROM base
)
SELECT bucket_order,
       delay_bucket,
       COUNT(*) AS orders,
       ROUND(AVG(score), 2) AS avg_review_score,
       ROUND(100.0 * AVG(score <= 2), 1) AS pct_low_reviews,
       ROUND(100.0 * AVG(score = 5), 1) AS pct_five_star,
       ROUND(AVG(delay), 1) AS avg_delay_days
FROM combined
GROUP BY bucket_order, delay_bucket
ORDER BY bucket_order;
