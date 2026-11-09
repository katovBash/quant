# third-touch-line

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1H, 4H; 51022 пар «акция × интервал × вариант». Ошибок расчёта: 0. | кандидат не зарегистрирован |

## Гипотеза и контроль

After two causally confirmed same-side ZigZag pivots define a support or resistance line, the first later third contact may create a tradable bounce or breakout in either price-trend direction. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 2134 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Вывод по входу

Полный перебор проверил два типа третьего касания (отскок и пробой) на линиях текущего графика, 1D и 1W. Для выбранного общего варианта `z3_5_4_0.5_100_d_x` автоматический отбор нашёл 9 акций вместо требуемых 10; медианная доходность месяца на раннем периоде после модельных расходов составляет лишь +0,03%. Новый paper trading не запущен. [Решение отбора](results/PAPER_REVIEW.md).
