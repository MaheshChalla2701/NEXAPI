-- SYNTHETIC SCENARIO - Retention dashboard (as written by the company's analytics team).
-- "30-day retention": share of a quarter's new workspaces with activity in their first 30 days
-- after sign-up. Activity comes from workspace_daily_activity (built by scripts/build_warehouse.py).
SELECT quarter,
       COUNT(*) AS new_workspaces,
       SUM(retained) AS retained_workspaces,
       ROUND(100.0 * SUM(retained) / COUNT(*), 1) AS retention_30d_pct
FROM (
    SELECT w.workspace_id,
           strftime('%Y', w.created_at) || '-Q' || ((CAST(strftime('%m', w.created_at) AS INTEGER) + 2) / 3) AS quarter,
           EXISTS (
               SELECT 1 FROM workspace_daily_activity a
               WHERE a.workspace_id = w.workspace_id
                 AND a.activity_date BETWEEN date(w.created_at, '+1 day') AND date(w.created_at, '+30 day')
           ) AS retained
    FROM workspaces w
    WHERE w.created_at >= '2026-04-01' AND w.created_at < '2026-10-01'
)
GROUP BY quarter
ORDER BY quarter;
