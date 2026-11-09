# confirmed-parallel-channel-bounce

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 319 акций, 1D; 4466 пар «акция × интервал × вариант». Ошибок расчёта: 0. | зарегистрированы виртуальные счета |

## Гипотеза и контроль

A daily ZigZag structure with two confirmed highs and one confirmed intervening low (or two lows and one high) defines parallel resistance and support. A completed candle rejecting either extreme produces a trade away from that boundary. Compare candle confirmation and 5%, 8%, opposite-line exits against the previous two-same-side-line rule. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 154 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: 4147 выбранных примеров; вся сетка не пересчитана. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Визуальный вариант Band-ZigZag

[Pine для ручной проверки](band_zigzag_channel_preview.pine) повторяет способ построения
ломаной из присланного Trendoscope Band-ZigZag: точка возникает при касании
границы полосы, а последний экстремум может уточняться. Поверх неё проведены
параллельные границы канала и показаны сигналы отбоя на закрытой дневной свече.
Этот вариант ещё не включён в расчёт выше и не подключён к paper trading:
отдельная сверка Python/Pine и полный исторический прогон не выполнены.

[Недельный Pine с ранним сигналом изгиба](band_zigzag_weekly_turn_review.pine)
отмечает первую закрытую неделю роста после нижней точки Band-ZigZag и
симметричную неделю падения после верхней. Маркер сигнала стоит на неделе,
когда поворот стал наблюдаемым; приказ в модели исполняется на открытии
следующей недели. Окончательная точка ломаной может смещаться, поэтому её
историческое положение нельзя использовать как цену входа без заглядывания
в будущее. Этот недельный вариант также не прошёл полный эксперимент.
Подпись вида `128.25%/111.32%` в исходном индикаторе показывает отношение
движений ZigZag и положение относительно полос, а не цену инструмента.

