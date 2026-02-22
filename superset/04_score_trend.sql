-- Датасет: 8-дневный скор — динамика
-- Chart type: Line Chart
-- X axis: report_date, Series: webmaster, Metric: score_pct
-- Добавь reference line на 100% (целевой скор)
-- Добавь reference line на 70% (минимальный порог)

SELECT
    webmaster,
    DATE(created_at AT TIME ZONE 'UTC')  AS report_date,
    ROUND(score_pct::numeric, 1)         AS score_pct,
    ROUND(buyout_pct::numeric, 1)        AS adj_buyout_pct,
    period_days
FROM webmaster_reports
WHERE score_pct IS NOT NULL
ORDER BY created_at DESC
