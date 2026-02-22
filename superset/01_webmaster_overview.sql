-- Датасет: Обзор вебмастеров (таблица с подсветкой)
-- Chart type: Table
-- Условное форматирование: health_score → градиент 0 (красный) → 100 (зелёный)
-- Условное форматирование: status → OK=зелёный, Warning=жёлтый, Critical=красный

SELECT
    webmaster,
    leads_total,
    approved,
    bought_out,
    trash,

    ROUND(approve_pct::numeric, 1)      AS approve_pct,
    ROUND(avg_approve_pct::numeric, 1)  AS avg_approve_pct,
    ROUND(adj_buyout_pct::numeric, 1)   AS adj_buyout_pct,
    ROUND(trash_pct::numeric, 1)        AS trash_pct,
    ROUND(avg_trash_pct::numeric, 1)    AS avg_trash_pct,
    ROUND(score_pct::numeric, 1)        AS score_pct,

    json_array_length(issues::json)     AS issues_count,
    issues,
    updated_at,

    -- Сводный балл здоровья 0–100 (основа для градиента)
    GREATEST(0, LEAST(100, ROUND((
        LEAST(approve_pct  / 30.0, 1.0) * 33 +
        LEAST(adj_buyout_pct / 65.0, 1.0) * 34 +
        GREATEST(0.0, (20.0 - trash_pct) / 20.0) * 33
    )::numeric, 1))) AS health_score,

    -- Статус для цветовой метки
    CASE
        WHEN ok AND GREATEST(0, LEAST(100, ROUND((
            LEAST(approve_pct  / 30.0, 1.0) * 33 +
            LEAST(adj_buyout_pct / 65.0, 1.0) * 34 +
            GREATEST(0.0, (20.0 - trash_pct) / 20.0) * 33
        )::numeric, 1))) >= 80 THEN 'OK'
        WHEN GREATEST(0, LEAST(100, ROUND((
            LEAST(approve_pct  / 30.0, 1.0) * 33 +
            LEAST(adj_buyout_pct / 65.0, 1.0) * 34 +
            GREATEST(0.0, (20.0 - trash_pct) / 20.0) * 33
        )::numeric, 1))) >= 50 THEN 'Warning'
        ELSE 'Critical'
    END AS status

FROM webmaster_status
ORDER BY health_score ASC   -- проблемные вверху
