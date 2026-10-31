-- PAWLY analysis marts (DuckDB).
-- Built by src/build_marts.py from the observed geo-day table (`obs`) and the
-- geo-test assignment (`asg`). Each table feeds one or more chapters.

-- 1. National daily totals: chapters 2 (causal impact) and 3 (auto-bidding).
CREATE OR REPLACE TABLE national_day AS
SELECT
    date,
    week,
    SUM(revenue)                    AS revenue,
    SUM(category_search_index)      AS category_search_index,
    SUM(brand_search_volume)        AS brand_search_volume,
    SUM(spend_brand_search)         AS spend_brand_search,
    SUM(spend_nonbrand_search)      AS spend_nonbrand_search,
    SUM(spend_auto_bid)             AS spend_auto_bid,
    SUM(spend_short_video)          AS spend_short_video,
    SUM(spend_social)               AS spend_social,
    SUM(spend_retargeting)          AS spend_retargeting,
    SUM(reported_rev_brand_search)  AS reported_rev_brand_search,
    SUM(reported_rev_nonbrand_search) AS reported_rev_nonbrand_search,
    SUM(reported_rev_auto_bid)      AS reported_rev_auto_bid,
    SUM(spend_brand_search + spend_nonbrand_search + spend_auto_bid) AS search_spend,
    SUM(reported_rev_brand_search + reported_rev_nonbrand_search + reported_rev_auto_bid) AS search_reported,
    SUM(spend_brand_search + spend_nonbrand_search + spend_auto_bid
        + spend_short_video + spend_social + spend_retargeting) AS ad_spend
FROM obs
GROUP BY date, week
ORDER BY date;

-- 2. National weekly totals for the media mix model: chapter 4.
--    Money in million KRW; search = brand + non-brand + auto-bidding;
--    category searches scaled to an average of 1.
CREATE OR REPLACE TABLE national_week AS
WITH w AS (
    SELECT
        week,
        SUM(revenue) / 1e6                AS revenue,
        SUM(category_search_index)        AS category_raw,
        SUM(spend_brand_search + spend_nonbrand_search + spend_auto_bid) / 1e6 AS search,
        SUM(spend_short_video) / 1e6      AS short_video,
        SUM(spend_social) / 1e6           AS social,
        SUM(spend_retargeting) / 1e6      AS retargeting
    FROM obs
    GROUP BY week
)
SELECT
    week, revenue,
    category_raw / AVG(category_raw) OVER () AS category,
    search, short_video, social, retargeting
FROM w
ORDER BY week;

-- 3. Geo test pair diagnostic: chapter 1.
--    For each matched pair, the change in the go-dark / control revenue ratio
--    from the 84 days before the test to the 6 test weeks, then a robust z-score
--    (distance from the median in MAD units).
CREATE OR REPLACE TABLE geo_test_pairs AS
WITH bounds AS (
    SELECT MIN(date) FILTER (WHERE week = 79) AS test_start,
           MAX(date) FILTER (WHERE week = 84) AS test_end
    FROM obs
),
per_geo AS (
    SELECT
        a.pair, a."group", o.geo,
        SUM(o.revenue) FILTER (WHERE o.date >= b.test_start - INTERVAL 84 DAY
                                 AND o.date <  b.test_start)          AS rev_pre,
        SUM(o.revenue) FILTER (WHERE o.date BETWEEN b.test_start AND b.test_end) AS rev_test
    FROM obs o
    JOIN asg a USING (geo)
    CROSS JOIN bounds b
    GROUP BY a.pair, a."group", o.geo
),
pairs AS (
    SELECT
        pair,
        MAX(geo) FILTER (WHERE "group" = 'go_dark') AS go_dark,
        MAX(geo) FILTER (WHERE "group" = 'control') AS control,
        LN(SUM(rev_test) FILTER (WHERE "group" = 'go_dark') / SUM(rev_test) FILTER (WHERE "group" = 'control'))
          - LN(SUM(rev_pre) FILTER (WHERE "group" = 'go_dark') / SUM(rev_pre) FILTER (WHERE "group" = 'control'))
          AS log_ratio_change
    FROM per_geo
    GROUP BY pair
),
med AS (SELECT MEDIAN(log_ratio_change) AS m FROM pairs),
mad AS (SELECT 1.4826 * MEDIAN(ABS(p.log_ratio_change - med.m)) AS s FROM pairs p, med)
SELECT p.*, (p.log_ratio_change - med.m) / mad.s AS robust_z
FROM pairs p, med, mad
ORDER BY pair;

-- 4. What each platform reports: the cross-platform view in chapter 4.
--    Each channel's own reported revenue and spend, by period.
CREATE OR REPLACE TABLE platform_claims AS
WITH long AS (
    SELECT week, 'search' AS channel,
           spend_brand_search + spend_nonbrand_search + spend_auto_bid AS spend,
           reported_rev_brand_search + reported_rev_nonbrand_search + reported_rev_auto_bid AS reported
    FROM obs
    UNION ALL SELECT week, 'short_video', spend_short_video, reported_rev_short_video FROM obs
    UNION ALL SELECT week, 'social',      spend_social,      reported_rev_social      FROM obs
    UNION ALL SELECT week, 'retargeting', spend_retargeting, reported_rev_retargeting FROM obs
)
SELECT
    CASE WHEN week <= 78 THEN 'weeks_1_78' ELSE 'weeks_79_104' END AS period,
    channel,
    SUM(spend)                 AS spend,
    SUM(reported)              AS reported,
    SUM(reported) / SUM(spend) AS reported_roas
FROM long
GROUP BY period, channel
ORDER BY period, channel;

-- 5. Total revenue by period, the denominator for "share of sales claimed by ads".
CREATE OR REPLACE TABLE period_revenue AS
SELECT CASE WHEN week <= 78 THEN 'weeks_1_78' ELSE 'weeks_79_104' END AS period,
       SUM(revenue) AS revenue
FROM obs
GROUP BY period
ORDER BY period;
