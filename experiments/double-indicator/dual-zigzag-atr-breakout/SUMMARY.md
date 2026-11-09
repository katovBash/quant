# dual-zigzag-atr-breakout

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1H, 4H; 2630 пар «акция × интервал × вариант». Ошибок расчёта: 0. | кандидат не зарегистрирован |

## Гипотеза и контроль

For the fixed 4H Dual ZigZag price/RSI trend rule, requiring the breakout close to clear the confirmed price pivot by 0.25, 0.5 or 1.0 previous-bar ATR(14) may reduce weak false-breakout losing trades. Test on both parent timeframes without retuning its price wing 5, deviation 2%, RSI 14 or exit. Measure lost winners as well as losers. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 110 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: 28 выбранных примеров; вся сетка не пересчитана. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Вывод по фильтру

ATR-порог 0.25/0.5/1 уменьшил абсолютное число убыточных сделок, но одновременно убрал почти столько же прибыльных входов и ухудшил доходность. По раннему рейтингу остался контроль `atr_0`; новый вариант к paper не предлагается. [Подробное сравнение](results/REPORT.md) и [пропущенные сделки](results/removed_parent_trades.csv).
