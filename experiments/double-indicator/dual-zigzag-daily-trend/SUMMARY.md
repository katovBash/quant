# dual-zigzag-daily-trend

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1H, 4H; 2630 пар «акция × интервал × вариант». Ошибок расчёта: 0. | зарегистрированы виртуальные счета |

## Гипотеза и контроль

For the frozen dual_5_2_14_trend-opp signal, rejecting long entries when the latest completed daily close is not above its daily SMA20 or SMA50 may cut more losing than winning long trades without degrading net return. Short entries remain. Short-only is an ablation. All exits use the original opposite event. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 110 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Вывод по фильтру

Выбран `4H sma_20`: по тем же семи акциям убыточных закрытых сделок 143 → 105, прибыльных 126 → 112; profit factor 2.02 → 2.29. Ранний рейтинг также поставил фильтр выше контроля. Восемь отдельных новых виртуальных счетов зарегистрированы; прежние семь не менялись. [Сравнение и ограничения](results/REPORT.md) · [все настройки и годовой порог](results/TARGET_20_REVIEW.md).
