<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `{{DATA_STATUS}}` | {{COVERAGE}} | {{PAPER_STATUS}} |

## Гипотеза и контроль

{{HYPOTHESIS}} [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: {{SNAPSHOT}}. Расходы: `{{COST_STATUS}}`. Корпоративные события: `{{CORPORATE_STATUS}}`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: {{GAP_PAIRS}} пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: {{SIDE_STATUS}}. Pine: {{PINE_STATUS}}. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->
