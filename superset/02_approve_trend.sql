-- Датасет: Динамика апрува по вебмастерам
-- Chart type: Line Chart
-- X axis: report_date, Series: webmaster, Metric: approve_pct
-- Добавь reference line на 30% (целевой апрув)

SELECT
    webmaster,
    DATE(created_at AT TIME ZONE 'UTC')  AS report_date,
    ROUND(approve_pct::numeric, 1)       AS approve_pct,
    ROUND(buyout_pct::numeric, 1)        AS adj_buyout_pct,
    ROUND(trash_pct::numeric, 1)         AS trash_pct,
    ROUND(score_pct::numeric, 1)         AS score_pct,
    json_array_length(issues::json)      AS issues_count,
    period_days
FROM webmaster_reports
ORDER BY created_at DESC
