# Turtle: только каналы входа

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 263 акций, 1D, 1H, 4H; 5523 пар «акция × интервал × вариант». Ошибок расчёта: 0. | кандидат не зарегистрирован |

## Гипотеза и контроль

Turtle upper/lower entry channels without separate upper/lower exit channels may reduce premature exits; reversal occurs only on an opposite entry-channel breakout. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, corporate actions, short borrow and exchange lots`. Корпоративные события: `partial`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 231 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

Проверка подсказки со скриншота: линии `upper entry` и `lower entry` работают как сигналы входа. Отдельные линии `upper exit` и `lower exit` отключены. Открытая позиция закрывается и переворачивается только при пробое противоположного канала входа.

[Протокол](protocol.json) зафиксирован до расчёта: длины канала 15, 20, 30, 40, 55, 70; контроль — действующее правило Turtle 55/20 с отдельным выходом 20. Все варианты используют одинаковые свечи, следующий open для исполнения, 1 млн ₽ на отдельный счёт, 25% размер позиции и эквивалент расходов 15 б.п. на сторону. Дивиденды и сплиты полностью не учтены; статус `REVIEW_ONLY`. На 1H и 4H период означает число свечей, а не дней.

Вселенная — все подходящие бумаги замороженного снимка MOEX 2026-10-30, интервалы 1D, 1H, 4H. 15M и 30M недоступны без минутных свечей. Полная сетка: 263 × 3 × 7 = 5523 пары до пропусков. Результаты сохраняются в `results/`, включая все убыточные случаи и месяцы. Работающий paper trading не меняется.

Из корня репозитория:

```bash
python3 experiments/turtle/entry-only/run.py --smoke
python3 experiments/turtle/entry-only/run.py
python3 skills/new-experiment/scripts/validate_run.py --protocol experiments/turtle/entry-only/protocol.json --results experiments/turtle/entry-only/results
python3 experiments/turtle/entry-only/analyze.py
```

[Сравнение с 55/20](results/COMPARISON.md) · [Итоговый отчёт](results/REPORT.md) · [Все варианты](results/all_variants.csv) · [Каждый месяц](results/monthly_returns.csv) · [Сводка по месяцам](results/monthly_case_summary.csv)
