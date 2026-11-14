# VTBR · недельный Band-ZigZag: подтверждение входа

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 1 акций, 1W; 10 пар «акция × интервал × вариант». Ошибок расчёта: 0. | кандидат не зарегистрирован |

## Гипотеза и контроль

For VTBR only, sustained weekly direction or weekly closes beyond SMA20 may remove false Band-ZigZag reversal entries; compare separately for long and short without changing the exit rule. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 0 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

Диагностический тест только на VTBR. `directional_2` повторяет вход исходного правила; выход по противоположному сигналу. Исполнение на открытии следующей недели, 1 млн ₽, размер позиции 25%, расходы 15 б.п. на сторону. Снимок MOEX ISS до 30.10.2026; 33 полных месяца с января 2024 по сентябрь 2026.

| Вход | Весь период | Последние 12 мес. | 2024 | 2025 | Закрытых | Плюс/все месяцы |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | -12.65% | -4.34% | -7.8584% | -1.4041% | 0 | 14/33 |
| `directional_2` | 1.44% | +15.20% | -9.4651% | -4.1066% | 4 | 13/33 |
| `directional_3` | 0.68% | +5.99% | 0.0% | -4.4948% | 1 | 11/33 |
| `directional_4` | 6.45% | +8.12% | 0.0% | 0.0% | 0 | 3/33 |
| `sma20_2` | 4.11% | +5.51% | 0.0% | -0.8381% | 1 | 11/33 |
| `sma20_3` | -8.28% | -5.54% | 0.0% | -3.548% | 0 | 9/33 |
| `sma20_4` | -7.88% | -5.69% | 0.0% | -2.9875% | 0 | 9/33 |
| `combined_2` | 2.97% | +10.38% | 0.0% | -4.337% | 1 | 11/33 |
| `combined_3` | 0.0% | +0.00% | 0.0% | 0.0% | 0 | 0/33 |
| `combined_4` | 0.0% | +0.00% | 0.0% | 0.0% | 0 | 0/33 |

`directional_N`: N закрытий подряд в сторону разворота. `sma20_N`: N закрытий выше SMA20 после нижнего пивота / ниже после верхнего. `combined_N`: оба условия.

## Long и short отдельно

| Вариант | Направление | Доходность всего | Закрытых | Прибыльных |
| --- | --- | ---: | ---: | ---: |
| `directional_2` | long_only | -6.59% | 2 | 1 |
| `directional_2` | short_only | 8.6% | 2 | 1 |
| `directional_3` | long_only | -4.41% | 1 | 0 |
| `directional_3` | short_only | 5.3% | 0 | 0 |
| `directional_4` | long_only | 0.0% | 0 | 0 |
| `directional_4` | short_only | 6.45% | 0 | 0 |
| `sma20_2` | long_only | -2.66% | 1 | 0 |
| `sma20_2` | short_only | 6.95% | 0 | 0 |
| `sma20_3` | long_only | -8.28% | 0 | 0 |
| `sma20_3` | short_only | 0.0% | 0 | 0 |
| `sma20_4` | long_only | -7.88% | 0 | 0 |
| `sma20_4` | short_only | 0.0% | 0 | 0 |
| `combined_2` | long_only | -3.27% | 1 | 0 |
| `combined_2` | short_only | 6.45% | 0 | 0 |
| `combined_3` | long_only | 0.0% | 0 | 0 |
| `combined_3` | short_only | 0.0% | 0 | 0 |
| `combined_4` | long_only | 0.0% | 0 | 0 |
| `combined_4` | short_only | 0.0% | 0 | 0 |

## Вывод

`directional_4`: +6,45% за весь период и +8,12% за последние 12 месяцев, но 0 закрытых сделок. Это переоценка открытой позиции; в 2024 и 2025 вариант не торговал. `combined_3/4` не входили. Исходный вход `directional_2`: +1,44% за весь период, +15,20% за последние 12 месяцев, -9,47% в 2024, -4,11% в 2025. Long-only: -6,59% (1/2 прибыльных); short-only: +8,60% (1/2). Выбор правила по одной акции и просмотренной истории был бы подгонкой.

Статус `REVIEW_ONLY`. Пайплайн оставил `REVIEW_REQUIRED`; новое правило и виртуальные счета не зарегистрированы. Дивиденды/сплиты и сверка Pine с Python не подтверждены.

[Все варианты](results/all_variants.csv) · [Помесячные результаты](results/monthly_returns.csv) · [Long/short](results/direction_summary.csv) · [Pine для ручной проверки](review.pine) · [Пайплайн](results/PIPELINE.json).

## Проверяемые результаты

[Помесячный отчёт](results/REPORT.md) · [Проверка данных](results/validation.json) · [Решение для paper](results/PAPER_REVIEW.md) · [Статус Pine](results/PINE_STATUS.json).
