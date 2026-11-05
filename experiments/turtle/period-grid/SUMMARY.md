# Перебор периодов Turtle

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1D, 1H, 4H; 15780 пар «акция × интервал × вариант». Ошибок расчёта: 0. | зарегистрированы виртуальные счета |

## Гипотеза и контроль

Nearby breakout and exit windows may reduce whipsaw while retaining monthly returns; test the full grid, not only the best historical ticker. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, corporate actions, short borrow and exchange lots`. Корпоративные события: `partial`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 660 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

Проверяем, как длина пробоя и выхода влияет на число сделок, месячный PnL и устойчивость правила. Это отдельный исследовательский эксперимент; работающий вариант `55/20` в paper trading не меняется.

Фиксированный [протокол](protocol.json): 19 пар из входов 15, 20, 30, 40, 55, 70 и выходов 5, 10, 20, 30 при условии выход < вход, плюс контроль buy and hold. Сравнение на одинаковых бумагах и свечах 1D, 1H, 4H. Сигнал подтверждается закрытием, исполнение на следующем открытии; текущий paper runner исполняет позже, на закрытии следующей наблюдаемой свечи. Эквивалент затрат — 5 б.п. комиссии и 10 б.п. проскальзывания на сторону; дивиденды, корпоративные события, лоты и стоимость шорта не моделируются. Размер 25% на независимый счёт 1 млн ₽, как в исходном эксперименте, поэтому результаты нельзя напрямую сложить в общий портфель или сравнить с 10% paper-счётом.

Вселенная определяется наличием данных из снимка 2026-10-30, без отбора по доходности. Для 15M/30M минутных исходников нет. Период с 2026-01-01 помечен `seen_history`, а не независимым тестом.

Из корня репозитория:

```bash
python3 experiments/turtle/period-grid/run.py --smoke
python3 experiments/turtle/period-grid/run.py
```

После прогона см. [общий отчёт](results/REPORT.md), [текущие 10 акций на трёх интервалах](results/TOP10_REVIEW.md), [проверку по времени и расходам](results/WALK_FORWARD_REVIEW.md), [все варианты](results/all_variants.csv), [каждый месяц](results/monthly_returns.csv), [сводку по парам](results/monthly_case_summary.csv), [годы](results/yearly_returns.csv), [окна по 100 сделок](results/trade_windows_100.csv), [покрытие](results/coverage.json) и [пропуски](results/skipped.csv). Статус расчёта — в `results/progress.csv`. Отчёты показывают результаты до любых решений о новой стратегии.

Дополнительные расчёты из корня проекта: `python3 experiments/turtle/period-grid/focus_top10.py` и `python3 experiments/turtle/period-grid/validate_grid.py`. Временные окна, правило выбора, соседние параметры и три сценария расходов зафиксированы в протоколе. История 2026 года уже просмотрена и не считается слепым подтверждением.
