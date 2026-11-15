# band-based-trend-filter-breakout

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 319 акций, 1H, 4H, 1D, 1W; 18496 пар «акция × интервал × вариант». Ошибок расчёта: 0. | зарегистрированы виртуальные счета |

## Гипотеза и контроль

Two or three separated closes beyond the same Bollinger band, with a return to the middle line between hits, may identify a persistent trend more reliably than a single band breakout. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 748 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: 3 выбранных примеров; вся сетка не пересчитана. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

Выбрано правило `bh_30_20_2_cross_opp · 1H`: повторное закрытие за одной полосой после возврата к SMA30; противоположные два касания меняют направление. За последние полные 12 месяцев после модельных расходов порог 10% прошли PHOR (+10,31%), MAGN (+19,23%) и TATNP (+12,98%). Поздняя история уже использована для допуска и не является независимым тестом. Три paper-счёта зарегистрированы и ожидают опроса.

[Раздельная диагностика long/short](results/trade_side_summary.csv) выполнена для выбранной настройки на трёх акциях, не для всей сетки. У MAGN большая часть исторического плюса пришлась на short; стоимость займа не учтена. [Python-сигналы](../../../strategies/trendoscope-band-hits-30-2-2-cross-opp-1h/parity.json) совпали с экспериментом на 537 проверенных барах. Pine в TradingView пока не сверялся.
