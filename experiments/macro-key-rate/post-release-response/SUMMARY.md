# post-release-response

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1H; 1841 пар «акция × интервал × вариант». Ошибок расчёта: 0. | закрыт после оценки |

## Гипотеза и контроль

After scheduled Bank of Russia key-rate releases, the first full hourly candle has a larger absolute return and volume than the same hour one week earlier; its direction may continue or reverse over the following 1, 3, or 6 bars. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 77 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

## Вывод по событию

На 20 из 23 дат решений ЦБ медианное абсолютное движение акций в 14:00–15:00 МСК превышало тот же час неделей ранее; медиана разницы по датам +0,0681 п.п., отношение объёмов 1,96. Это наблюдение о повышенной активности, без доказательства причины. Все шесть проверенных торговых правил дали отрицательную медианную среднемесячную доходность после расходов (−0,03…−0,05%), поэтому торговая гипотеза закрыта; [решение](results/decision.json) и [событийная таблица](results/event_date_summary.csv) сохранены.

