-- Датасет: Ежедневная разбивка лидов
-- Chart type: Bar Chart (stacked) или Line Chart
-- X axis: date, Series: webmaster
-- Metrics: total_leads, approved, bought_out, trash, approve_pct, buyout_pct

SELECT
    date,
    webmaster,
    COUNT(*)                                                          AS total_leads,

    SUM(CASE WHEN status IN (2,3,4,5,8,12,13,14) THEN 1 ELSE 0 END) AS approved,
    SUM(CASE WHEN status IN (3,4,8)              THEN 1 ELSE 0 END)  AS bought_out,
    SUM(CASE WHEN status = 18                    THEN 1 ELSE 0 END)  AS trash,

    ROUND(
        100.0 * SUM(CASE WHEN status IN (2,3,4,5,8,12,13,14) THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)::numeric, 1
    ) AS approve_pct,

    ROUND(
        100.0 * SUM(CASE WHEN status IN (3,4,8) THEN 1 ELSE 0 END)
        / NULLIF(
            SUM(CASE WHEN status IN (2,3,4,5,8,12,13,14) THEN 1 ELSE 0 END), 0
          )::numeric, 1
    ) AS buyout_pct,

    ROUND(
        100.0 * SUM(CASE WHEN status = 18 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0)::numeric, 1
    ) AS trash_pct

FROM leads
GROUP BY date, webmaster
ORDER BY date DESC, webmaster
