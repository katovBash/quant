# sma-band-close-breakout

<!-- experiment-summary:start -->
## Краткая сводка

| Статус данных | Покрытие | Решение по paper |
| --- | --- | --- |
| `REVIEW_ONLY` | 319 акций, 1H, 4H, 1D, 1W; 14144 пар «акция × интервал × вариант». Ошибок расчёта: 0. | зарегистрированы виртуальные счета |

## Гипотеза и контроль

A single completed close beyond the SMA Bollinger band may give timely long/short breakouts; test adjacent SMA lengths, band widths and one/two-close confirmations across all cached instruments and 1H/4H/1D/1W. [Протокол](protocol.json) фиксирует правило, контроль и параметры.

## Данные и ограничения

Снимок: MOEX ISS local snapshot 2026-10-30. Расходы: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`. Корпоративные события: `unchecked`; непроверенные выплаты и сплиты нельзя считать учтёнными. Календарные пропуски: 572 пар.

## Результат

[Помесячный отчёт](results/REPORT.md) · [все варианты](results/all_variants.csv) · [каждый месяц](results/monthly_returns.csv). Отчёт показывает последние 1/3/6/9/12 полных месяцев и отдельные календарные месяцы.

## Проверка и paper trading

Раздельный пересчёт long/short: не выполнен. Pine: AVAILABLE_FOR_REVIEW. [Проверка данных](results/validation.json) · [решение для paper](results/PAPER_REVIEW.md) · [статус Pine](results/PINE_STATUS.json).
<!-- experiment-summary:end -->

Итог пайплайна: `PAPER_REGISTERED`; 13 отдельных виртуальных счетов зарегистрированы и ожидают опроса терминальным процессом. Из 48 сочетаний интервала и параметров выбрано первое по раннему рейтингу с акциями выше индивидуального порога 10% за последние полные 12 месяцев после модельных расходов: `bb_30_15_1 · 1D` (SMA30, ширина 1,5σ, одно подтверждённое закрытие). Это отличается от исходного пользовательского примера SMA20 ± 2σ; он также есть в полной сетке. Поздняя история уже участвовала в допуске и не является независимой проверкой.

[Фиксированная стратегия](../../../strategies/sma-band-close-breakout-30-15-1-1d/strategy.py) · [Pine](../../../strategies/sma-band-close-breakout-30-15-1-1d/strategy.pine) · [сверка Python-сигналов](../../../strategies/sma-band-close-breakout-30-15-1-1d/parity.json). Компиляция и исполнение Pine в TradingView пока не сверены с Python; дивиденды и сплиты охвачены неполно. Для реальной торговли допуск не получен.

[Протокол](protocol.json) · [Манифест](results/manifest.json) · [Проверка данных](results/validation.json) · [Помесячный отчёт](results/REPORT.md) · [Решение о paper](results/PAPER_REVIEW.md) · [Pine статус](results/PINE_STATUS.json).
