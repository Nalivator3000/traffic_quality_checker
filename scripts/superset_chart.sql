-- Superset chart: Traffic Quality by Webmaster
-- Metrics: approve%, buyout%, trash%, 8d score, 30d score, cut flag, anomaly triggers
--
-- approve_pct   = approved / (total - trash) * 100   [треш исключён из знаменателя]
-- buyout_pct    = bought_out / approved * 100
-- trash_pct     = trash / total * 100
-- score_8d      = фактические выкупы / ожидаемые выкупы (бенчмарк по возрасту) за 8 дней
-- score_30d     = то же, но за 30 дней (лиды старше 8 дней → бенчмарк 75%)
--
-- Бенчмарки откалиброваны по фактической кривой выкупа из данных:
--   день 1: 40%  день 2: 45%  день 3: 55%  день 4: 60%
--   день 5: 65%  день 6: 67%  день 7: 72%  день 8+: 75%
-- score_3d_trend= взвешенный тренд (buyout 40% + approve 30% + trash 30%) vs собственный 30d-бейзлайн
--
-- Superset Conditional Formatting (score_8d_pct, score_30d_pct, score_3d_trend_pct):
--   < 70   → красный   (#DC3545)  — значительное отставание
--   70–90  → жёлтый   (#FFC107)  — под наблюдением
--   ≥ 90   → зелёный  (#28A745)  — норма / выше нормы
--
-- composite     = rank(score_30d)*0.7 + rank(approve)*0.2 + rank(1-trash)*0.1
-- cut_flag      = нижние 20% по composite → CUT, 20-40% → WATCH, остальные → OK
-- trigger_1d/3d = сравнение короткого окна с собственным 30d-бейзлайном вебмастера
--                 TRASH_UP:     trash_Nd > baseline_trash * 1.5  (аномальный рост треша)
--                 APPROVE_DOWN: approve_Nd < baseline_approve * 0.7  (аномальное падение апрува)

WITH
analysis_date AS (
    SELECT MAX(date) AS dt FROM leads
),

cohorts AS (
    SELECT
        l.webmaster,
        (ad.dt - l.date)                 AS age_days,
        COUNT(*)                         AS leads,
        SUM(CASE WHEN l.status IN (2,3,4,5,8,12,13,14) THEN 1 ELSE 0 END) AS approved,
        SUM(CASE WHEN l.status IN (3,4,8)               THEN 1 ELSE 0 END) AS bought_out,
        SUM(CASE WHEN l.status = 18                      THEN 1 ELSE 0 END) AS trash
    FROM leads l, analysis_date ad
    GROUP BY l.webmaster, l.date, ad.dt
),

summary AS (
    SELECT
        webmaster,
        SUM(leads)      AS total_leads,
        SUM(approved)   AS total_approved,
        SUM(bought_out) AS total_bought_out,
        SUM(trash)      AS total_trash,
        -- Короткие окна для триггеров аномалий
        SUM(CASE WHEN age_days = 0                 THEN leads    ELSE 0 END) AS leads_1d,
        SUM(CASE WHEN age_days = 0                 THEN approved ELSE 0 END) AS approved_1d,
        SUM(CASE WHEN age_days = 0                 THEN trash    ELSE 0 END) AS trash_1d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 2     THEN leads    ELSE 0 END) AS leads_3d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 2     THEN approved ELSE 0 END) AS approved_3d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 2     THEN trash    ELSE 0 END) AS trash_3d
    FROM cohorts
    GROUP BY webmaster
),

scoring AS (
    SELECT
        webmaster,
        -- 8-дневное окно
        SUM(CASE WHEN age_days BETWEEN 0 AND 8 THEN leads     ELSE 0 END) AS window_leads_8d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 8 THEN bought_out ELSE 0 END)::float AS num_8d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 8 THEN
            approved * CASE GREATEST(1, age_days)
                WHEN 1 THEN 0.40 WHEN 2 THEN 0.45 WHEN 3 THEN 0.55
                WHEN 4 THEN 0.60 WHEN 5 THEN 0.65 WHEN 6 THEN 0.67
                WHEN 7 THEN 0.72 WHEN 8 THEN 0.75
            END
        ELSE 0 END)::float AS den_8d,
        -- 3-дневное окно (для trigger_3d — buyout-компонент)
        SUM(CASE WHEN age_days BETWEEN 0 AND 2 THEN leads     ELSE 0 END) AS window_leads_3d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 2 THEN bought_out ELSE 0 END)::float AS num_3d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 2 THEN
            approved * CASE GREATEST(1, age_days)
                WHEN 1 THEN 0.40 WHEN 2 THEN 0.45 ELSE 0.40
            END
        ELSE 0 END)::float AS den_3d,
        -- 30-дневное окно (лиды старше 8 дней → бенчмарк фиксирован на 65%)
        SUM(CASE WHEN age_days BETWEEN 0 AND 30 THEN leads     ELSE 0 END) AS window_leads_30d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 30 THEN bought_out ELSE 0 END)::float AS num_30d,
        SUM(CASE WHEN age_days BETWEEN 0 AND 30 THEN
            approved * CASE LEAST(GREATEST(1, age_days), 8)
                WHEN 1 THEN 0.40 WHEN 2 THEN 0.45 WHEN 3 THEN 0.55
                WHEN 4 THEN 0.60 WHEN 5 THEN 0.65 WHEN 6 THEN 0.67
                WHEN 7 THEN 0.72 WHEN 8 THEN 0.75
            END
        ELSE 0 END)::float AS den_30d
    FROM cohorts
    GROUP BY webmaster
),

-- Составной скор для cut_flag: только вебмастера с >= 30 лидов
composite AS (
    SELECT
        s.webmaster,
        -- Основной сигнал качества: score_30d если данных достаточно,
        -- иначе fallback на сырой buyout_pct (оба уже в %, сопоставимы)
        COALESCE(
            CASE WHEN sc.window_leads_30d >= 50 AND sc.den_30d > 0
                 THEN sc.num_30d / sc.den_30d * 100 END,
            100.0 * s.total_bought_out / NULLIF(s.total_approved, 0),
            0
        ) AS quality_score,
        COALESCE(100.0 * s.total_approved   / NULLIF(s.total_leads - s.total_trash, 0), 0) AS approve_pct,
        COALESCE(100.0 * s.total_trash      / NULLIF(s.total_leads, 0), 0)                  AS trash_pct
    FROM summary s
    LEFT JOIN scoring sc ON s.webmaster = sc.webmaster
    WHERE s.total_leads >= 30
),

ranked AS (
    SELECT
        webmaster,
        -- 0 = худший, 1 = лучший по каждой метрике
        PERCENT_RANK() OVER (ORDER BY quality_score ASC) AS r_buyout,
        PERCENT_RANK() OVER (ORDER BY approve_pct   ASC) AS r_approve,
        PERCENT_RANK() OVER (ORDER BY trash_pct     DESC) AS r_trash
    FROM composite
),

cut_scores AS (
    SELECT
        webmaster,
        ROUND((0.7 * r_buyout + 0.2 * r_approve + 0.1 * r_trash)::numeric, 3) AS composite_score,
        PERCENT_RANK() OVER (
            ORDER BY (0.7 * r_buyout + 0.2 * r_approve + 0.1 * r_trash) ASC
        ) AS composite_rank
    FROM ranked
)

SELECT
    s.webmaster,
    s.total_leads,

    -- Основные метрики
    ROUND(COALESCE(100.0 * s.total_approved   / NULLIF(s.total_leads - s.total_trash, 0), 0)::numeric, 1) AS approve_pct,
    ROUND(COALESCE(100.0 * s.total_bought_out / NULLIF(s.total_approved, 0), 0)::numeric, 1)              AS buyout_pct,
    ROUND(COALESCE(100.0 * s.total_trash      / NULLIF(s.total_leads, 0), 0)::numeric, 1)                 AS trash_pct,

    -- 8-дневный скор (NULL если < 30 лидов в окне)
    CASE WHEN sc.window_leads_8d >= 30 AND sc.den_8d > 0
         THEN ROUND((sc.num_8d / sc.den_8d * 100)::numeric, 1)
    END AS score_8d_pct,

    -- 30-дневный скор (NULL если < 50 лидов в окне)
    CASE WHEN sc.window_leads_30d >= 50 AND sc.den_30d > 0
         THEN ROUND((sc.num_30d / sc.den_30d * 100)::numeric, 1)
    END AS score_30d_pct,

    -- Составной скор и решение об обрезании
    cs.composite_score,
    CASE
        WHEN cs.composite_rank IS NULL   THEN '⬜ NO DATA'   -- < 30 лидов
        WHEN cs.composite_rank < 0.20    THEN '🔴 CUT'       -- нижние 20%
        WHEN cs.composite_rank < 0.40    THEN '🟡 WATCH'     -- 20–40%
        ELSE                                  '🟢 OK'
    END AS cut_flag,

    -- Показатели коротких окон (NULL если недостаточно лидов)
    CASE WHEN s.leads_1d >= 5 THEN ROUND((100.0 * s.trash_1d    / NULLIF(s.leads_1d, 0))::numeric, 1) END AS trash_1d_pct,
    CASE WHEN s.leads_1d >= 5 THEN ROUND((100.0 * s.approved_1d / NULLIF(s.leads_1d - s.trash_1d, 0))::numeric, 1) END AS approve_1d_pct,
    CASE WHEN s.leads_3d >= 10 THEN ROUND((100.0 * s.trash_3d   / NULLIF(s.leads_3d, 0))::numeric, 1) END AS trash_3d_pct,
    CASE WHEN s.leads_3d >= 10 THEN ROUND((100.0 * s.approved_3d / NULLIF(s.leads_3d - s.trash_3d, 0))::numeric, 1) END AS approve_3d_pct,

    -- Триггер 1d: только треш и апрув — выкуп за 1 день ненадёжен (мин. 5 лидов)
    CASE WHEN s.leads_1d >= 5 THEN
        NULLIF(TRIM(BOTH ' | ' FROM CONCAT_WS(' | ',
            CASE WHEN s.trash_1d::float / NULLIF(s.leads_1d, 0)
                      > (s.total_trash::float / NULLIF(s.total_leads, 0)) * 1.5
                 THEN 'TRASH_UP' END,
            CASE WHEN s.approved_1d::float / NULLIF(s.leads_1d - s.trash_1d, 0)
                      < (s.total_approved::float / NULLIF(s.total_leads - s.total_trash, 0)) * 0.7
                 THEN 'APPROVE_DOWN' END
        )), '')
    END AS trigger_1d,

    -- Severity для цветовой подсветки trigger_1d: 0=норма 1=один флаг 2=оба флага
    CASE WHEN s.leads_1d >= 5 THEN
        (CASE WHEN s.trash_1d::float / NULLIF(s.leads_1d, 0)
                   > (s.total_trash::float / NULLIF(s.total_leads, 0)) * 1.5    THEN 1 ELSE 0 END
       + CASE WHEN s.approved_1d::float / NULLIF(s.leads_1d - s.trash_1d, 0)
                   < (s.total_approved::float / NULLIF(s.total_leads - s.total_trash, 0)) * 0.7 THEN 1 ELSE 0 END)
    ELSE 0 END AS trigger_1d_severity,

    -- Скор 3d: взвешенное соотношение 3d-показателей к собственному 30d-бейзлайну
    -- 100% = как обычно, <100% = деградация, >100% = улучшение
    -- buyout (40%): score_3d / score_30d
    -- approve (30%): approve_3d / approve_30d
    -- trash (30%): (1 - trash_3d%) / (1 - trash_30d%)
    CASE WHEN s.leads_3d >= 10 AND sc.den_30d > 0 AND sc.den_3d > 0 THEN
        ROUND(((
            0.4 * COALESCE((sc.num_3d / NULLIF(sc.den_3d, 0))
                         / NULLIF(sc.num_30d / NULLIF(sc.den_30d, 0), 0), 1)
          + 0.3 * COALESCE((s.approved_3d::float / NULLIF(s.leads_3d - s.trash_3d, 0))
                         / NULLIF(s.total_approved::float / NULLIF(s.total_leads - s.total_trash, 0), 0), 1)
          + 0.3 * COALESCE((1 - s.trash_3d::float / NULLIF(s.leads_3d, 0))
                         / NULLIF(1 - s.total_trash::float / NULLIF(s.total_leads, 0), 0), 1)
        ) * 100)::numeric, 1)
    END AS score_3d_trend_pct,

    -- Точечные флаги (пороги откалиброваны по P25/P75 реальных данных)
    CASE WHEN ROUND(COALESCE(100.0 * s.total_approved / NULLIF(s.total_leads - s.total_trash, 0), 0)::numeric, 1) < 16
         THEN 'LOW APPROVE' END AS flag_approve,
    CASE WHEN ROUND(COALESCE(100.0 * s.total_trash / NULLIF(s.total_leads, 0), 0)::numeric, 1) > 40
         THEN 'HIGH TRASH'  END AS flag_trash,
    CASE WHEN sc.window_leads_8d >= 30 AND sc.den_8d > 0 AND (sc.num_8d / sc.den_8d) < 0.5
         THEN 'LOW SCORE'   END AS flag_score

FROM summary s
LEFT JOIN scoring    sc ON s.webmaster = sc.webmaster
LEFT JOIN cut_scores cs ON s.webmaster = cs.webmaster
WHERE s.total_leads >= 5
ORDER BY cs.composite_score ASC NULLS LAST
