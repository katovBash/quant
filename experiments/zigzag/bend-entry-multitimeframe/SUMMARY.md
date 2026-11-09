# bend-entry-multitimeframe

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 319 акций, 15M, 30M, 1H, 4H, 1D; 139425 пар «акция × интервал × вариант». Ошибок расчёта: 0. | кандидат не зарегистрирован |

## Гипотеза и контроль

A band-extreme rejection at delay 0, or a reversal confirmation at every integer delay from 1 to 20 completed bars without a new extreme, may identify causal ZigZag bends across intraday and daily intervals. Leg ratio and wick are factorial filters. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 5445 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Область проверенного перебора

Проверены все 164 заявленные настройки входа и контроль: задержка 0 на свече изгиба, затем каждое целое ожидание от 1 до 20 свечей для подтверждений `close` и `break`, с двумя порогами длины плеча и двумя порогами тени. Реальные расчёты есть для 1H (263 акции), 4H (263) и 1D (319). На 15M и 30M исходных минутных свечей нет; это `SOURCE_MISSING`, а не отрицательный результат стратегии.

Лучшие медианы доходности за полный 2025 год по всем доступным акциям: 1H +1,10%, 4H +1,78%, 1D +2,78%. Эти значения получены после перебора и не служат независимым подтверждением. Pine не сверен по сделкам с Python, поэтому виртуальные счета не создавались.

