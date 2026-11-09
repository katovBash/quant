# dual-zigzag-sma-obv-confirmation

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1H, 4H; 4208 пар «акция × интервал × вариант». Ошибок расчёта: 0. | зарегистрированы виртуальные счета |

## Гипотеза и контроль

OBV net flow over 5, 10 or 20 completed signal bars may confirm fixed Dual ZigZag + daily SMA20 entries and reject more eventual losing than winning trades. Measure changes in PnL, monthly outcomes and risk; standalone OBV-crossing is an ablation. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 176 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: 56 выбранных примеров; вся сетка не пересчитана. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Вывод по третьему индикатору

OBV(10) занял первое место раннего рейтинга, но на тех же восьми бумагах SMA20 число убытков выросло 129 → 131, profit factor упал 2.19 → 2.08. Поэтому OBV не принят как улучшение текущей стратегии. Девять отдельных виртуальных счетов зарегистрированы лишь для наблюдения; старые счета не изменены. [Подробности](results/REPORT.md) · [все настройки и годовой порог](results/TARGET_20_REVIEW.md).
