-- Датасет: Тепловая карта проблем по вебмастерам и датам
-- Chart type: Heatmap или Table
-- Показывает кол-во проблем по каждому вебу в каждую дату прогона

SELECT
    webmaster,
    DATE(created_at AT TIME ZONE 'UTC')  AS report_date,
    json_array_length(issues::json)       AS issues_count,
    ROUND(approve_pct::numeric, 1)        AS approve_pct,
    ROUND(buyout_pct::numeric, 1)         AS adj_buyout_pct,
    ROUND(trash_pct::numeric, 1)          AS trash_pct,
    ROUND(score_pct::numeric, 1)          AS score_pct,
    issues,

    CASE
        WHEN json_array_length(issues::json) = 0 THEN 'OK'
        WHEN json_array_length(issues::json) = 1 THEN 'Warning'
        ELSE 'Critical'
    END AS status

FROM webmaster_reports
ORDER BY created_at DESC, webmaster
