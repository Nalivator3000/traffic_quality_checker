-- Датасет: Распределение лидов по CRM-статусам
-- Chart type: Pie или Bar
-- Полезно для понимания структуры потока

SELECT
    webmaster,
    status,
    CASE status
        WHEN 0  THEN 'Новый'
        WHEN 1  THEN 'Обработан'
        WHEN 2  THEN 'Отправлен'
        WHEN 3  THEN 'Доставлен'
        WHEN 4  THEN 'Вручен'
        WHEN 5  THEN 'Возврат'
        WHEN 6  THEN 'Отменён'
        WHEN 7  THEN 'Удалён'
        WHEN 8  THEN 'Оплачен'
        WHEN 9  THEN 'Недозвон'
        WHEN 10 THEN 'Перезвон'
        WHEN 12 THEN 'Вруч-Возврат'
        WHEN 13 THEN 'Контрольный прозвон'
        WHEN 14 THEN 'Ожидает отправки'
        WHEN 17 THEN 'Отказ'
        WHEN 18 THEN 'Треш'
        WHEN 24 THEN 'Отказ (нестандартный)'
        WHEN 27 THEN 'Ожидает поставки'
        WHEN 29 THEN 'Перезвон'
        ELSE 'Статус ' || status::text
    END AS status_name,

    CASE
        WHEN status IN (3,4,8)              THEN 'Выкуп'
        WHEN status IN (2,5,12,13,14)       THEN 'Апрув (не выкуп)'
        WHEN status = 18                    THEN 'Треш'
        WHEN status IN (6,9,10,17,24,29)    THEN 'Отказ'
        ELSE 'Прочее'
    END AS category,

    COUNT(*) AS leads_count

FROM leads
GROUP BY webmaster, status
ORDER BY webmaster, leads_count DESC
