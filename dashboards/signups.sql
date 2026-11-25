-- SYNTHETIC SCENARIO - Sign-ups dashboard (as written by the company's analytics team).
-- New workspaces per quarter and change against the previous quarter.
WITH q AS (
    SELECT strftime('%Y', created_at) || '-Q' || ((CAST(strftime('%m', created_at) AS INTEGER) + 2) / 3) AS quarter,
           COUNT(*) AS signups
    FROM workspaces
    WHERE created_at >= '2025-01-01'
    GROUP BY 1
)
SELECT quarter,
       signups,
       ROUND(100.0 * (signups * 1.0 / LAG(signups) OVER (ORDER BY quarter) - 1), 1) AS change_vs_prev_quarter_pct
FROM q
ORDER BY quarter;
