# published-decision-direction

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1H; 3419 пар «акция × интервал × вариант». Ошибок расчёта: 0. | закрыт после оценки |

## Гипотеза и контроль

The published direction of a scheduled Bank of Russia key-rate decision (hike, cut, hold) may predict 1H equity returns after the information is public. Test conventional and inverse mappings and explicit hold-day choices, without using the candle move to choose direction. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 143 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Вывод по опубликованному решению

Проверены 23 решения ЦБ (3 повышения, 10 снижений, 10 сохранений ставки) на 263 акциях. Направление сделки задавалось опубликованной ставкой, вход — в 15:00 МСК после целой часовой свечи. Все 12 правил дали отрицательную медианную среднемесячную доходность после расходов (−0,02…−0,06%); [торговая гипотеза закрыта](results/decision.json). [Отчёт по датам](results/decision_date_summary.csv) сохраняет полезный разбор реакции. Исторических ожиданий рынка нет, поэтому нельзя назвать изменение ставки неожиданным для рынка.

