# connors-turtle-soup

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1D, 1H, 4H; 7101 пар «акция × интервал × вариант». Ошибок расчёта: 0. | кандидат не зарегистрирован |

## Гипотеза и контроль

A false breakout through a prior channel extreme followed by a close back inside may produce short reversals with a higher share of profitable months than buy-and-hold on the same instruments. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `partial`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 297 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

Статус проверки: `REVIEW_ONLY`. Результаты и решение лежат в одном комплекте файлов.

[Протокол](protocol.json) · [Манифест](results/manifest.json) · [Проверка данных](results/validation.json) · [Помесячный отчёт](results/REPORT.md) · [Решение о paper](results/PAPER_REVIEW.md) · [Pine статус](results/PINE_STATUS.json).
