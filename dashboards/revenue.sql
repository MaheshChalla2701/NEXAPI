-- SYNTHETIC SCENARIO - Revenue dashboard (as written by the company's analytics team).
-- Quarterly revenue in USD and change against the previous quarter.
-- Revenue = successful charges, converted to USD at the month's average rate.
WITH q AS (
    SELECT strftime('%Y', p.created_at) || '-Q' || ((CAST(strftime('%m', p.created_at) AS INTEGER) + 2) / 3) AS quarter,
           SUM(p.amount * fx.usd_per_unit) AS revenue_usd
    FROM payments p
    JOIN fx_rates fx
      ON fx.currency = p.currency
     AND fx.month = strftime('%Y-%m', p.created_at)
    WHERE p.status = 'succeeded'
      AND p.type = 'charge'
    GROUP BY 1
)
SELECT quarter,
       ROUND(revenue_usd, 2) AS revenue_usd,
       ROUND(100.0 * (revenue_usd / LAG(revenue_usd) OVER (ORDER BY quarter) - 1), 1) AS change_vs_prev_quarter_pct
FROM q
ORDER BY quarter;
