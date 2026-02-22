# Superset — SQL датасеты

## Как добавить датасет
1. Superset → **SQL Lab → SQL Editor** → вставить запрос → Run
2. **Save as Dataset** → дать имя
3. Создать Chart на основе датасета

## Датасеты

| Файл | Датасет | Рекомендуемый тип чарта |
|------|---------|------------------------|
| `01_webmaster_overview.sql` | Обзор вебов | **Table** с conditional formatting |
| `02_approve_trend.sql` | Динамика метрик | **Line Chart** |
| `03_daily_leads.sql` | Ежедневные лиды | **Bar Chart** / **Line Chart** |
| `04_score_trend.sql` | 8-дневный скор | **Line Chart** |
| `05_issues_heatmap.sql` | Тепловая карта проблем | **Heatmap** / **Table** |
| `06_status_distribution.sql` | Распределение статусов | **Pie** / **Bar** |

## Настройка цветов в Table (01_webmaster_overview)

В Chart Editor → **Customize → Conditional formatting:**

### Колонка `health_score`
- Colorscale: **RdYlGn** (красный → жёлтый → зелёный)
- Min: `0`, Max: `100`

### Колонка `status`
- Добавить 3 правила (String equality):
  - `OK`       → цвет `#52c41a` (зелёный)
  - `Warning`  → цвет `#faad14` (жёлтый)
  - `Critical` → цвет `#f5222d` (красный)

### Колонки `approve_pct`, `adj_buyout_pct`, `trash_pct`
- Можно добавить отдельные colorscale:
  - `approve_pct`:    Min=0 (красный) → Max=30+ (зелёный)
  - `adj_buyout_pct`: Min=0 (красный) → Max=65+ (зелёный)
  - `trash_pct`:      Min=0 (зелёный) → Max=20+ (красный)

## Пороги (reference lines для Line Charts)
- Апрув: 30%
- Выкуп: 65%
- Треш: 20%
- 8-дн. скор: 100% (цель) / 70% (минимум)
