# EMA grid search: periods 2–200

> Историческая запись: стратегии и виртуальные счета из этого исследования удалены 02.11.2026 после проверки месячного риска; результаты эксперимента сохранены.

Интервалы **15M и 30M** подключены к запуску этого эксперимента через минутные свечи MOEX. Исторические сводки выше относятся только к интервалам, фактически записанным в [manifest.json](results/manifest.json) и [progress.csv](results/progress.csv). Наличие исходных минутных данных проверяется в [общем JSON покрытия](../../data/moex_scan/minute_coverage.json); отсутствие данных означает отсутствие теста, а не нулевую доходность. Загрузчик: `python3 scripts/fetch_minute_snapshot.py`; после появления минутного снимка команду перебора для этого индикатора запускают с `--timeframes 15M 30M`.

## Статус и гипотеза

Статус: **расчёт завершён; фиксированный вариант пока не подтверждён на новых данных**. Проверяем, есть ли устойчивые области параметров пересечения EMA с положительным результатом после расходов. Контроль — EMA12/33 и покупка с удержанием на той же истории.

## Протокол и файлы

Проверки реализации: [тесты перебора и сверки ускоренного расчёта](../../tests/ema/test_ema_grid_kernel.py). Команда из корня проекта: `python3 -m unittest tests.ema.test_ema_grid_kernel -q`. Тесты проверяют код расчёта, а не будущую доходность найденной пары.

`run.py` выполняет полный перебор, `results/` хранит все строки по тикеру и интервалу, `candidate.json` фиксирует один вариант для ручной проверки. `coverage.py`, `fetch_hourly.py`, `analyze_robustness.py` и `validate_fixed_pair.py` отвечают соответственно за покрытие, загрузку недостающего кэша, обзор соседних пар и проверку выбранной пары без нового подбора. Снимок списка бумаг: [`data/moex_scan/universe_2026-10-30.json`](../../data/moex_scan/universe_2026-10-30.json).

## Результаты и решение

[Краткая сводка с примерами результатов](SUMMARY.md). Полные CSV находятся в `results/<таймфрейм>/<тикер>.csv.gz`; каждый содержит все пары и режимы, включая убытки.

[Первичный обзор устойчивости соседних параметров на PLZL, VTBR и GAZP](ROBUSTNESS.md) показывает области для следующей проверки. Он сделан на просмотренной истории и не меняет выбранную бумажную стратегию.

[Фиксированная EMA13/48 long+short на всех 254 доступных часовых рядах](results/fixed_13_48_1H_long_short.csv): 109 прибыльных, медиана доходности −6,56%. [Та же пара только long](results/fixed_13_48_1H_long.csv): 79 прибыльных. Это проверка на уже просмотренной истории, а не новое подтверждение. Ограниченный кандидат для ручной сверки PLZL, VTBR и GAZP **1H** находится в strategies; действующий бумажный процесс не изменён.

По предложенной соседней паре [EMA13/43 long+short](results/fixed_13_43_1H_long_short.csv) на тех же 254 рядах прибыльны 107 бумаг, медиана −8,27%; на PLZL, VTBR, GAZP соответственно +49,00%, +30,02%, +31,29%. Это остаётся отдельной строкой исследования, а не второй стратегией и не подтверждением универсальности.

This is **research**, not a running strategy or a paper trading account.

`run.py` scans every fast/slow pair with `2 <= fast < slow <= 200` (19,701 pairs) in three modes: long, short, and long+short. It uses the existing `src/ema/core/scan_ema.py` execution model: crossover on confirmed bar, order at next open, 25% of equity, 0.05% commission per side, one price tick of slippage, and marked-to-market open positions. `kernel.cpp` is a compiled acceleration of that model; PLZL 12/33 daily trades and returns were checked against the Python implementation. The older model rounds to integer shares rather than whole exchange lots; this sweep is exploratory and finalists must be recomputed with actual lots. Short borrow cost is not included.

The fixed research snapshot is MOEX TQBR candles through **2026-10-30**: daily data starts 2022-01-01; hourly data starts 2024-01-01. `4H` is assembled from groups of four available hourly candles per trading day. These bars may not align with TradingView's 4H bars. `SECTYPE` 1 and 2 are included as common/preferred shares; other instruments in the TQBR snapshot are excluded. `run.py` uses only cached candles; `fetch_hourly.py` can download missing hourly series separately.

The completed 2026-11-01 snapshot covers 258 current TQBR equity tickers: 255 daily series, 254 hourly series, and 254 derived 4H series. GAZC, GAZS, and GAZT have only two daily bars and no hourly bars; MGNZ has no hourly bars and its daily series ended in 2022. The daily MGNZ output exists for research reproducibility but has no new-data test. `results/coverage.json` contains the exact exclusions and current-universe comparison.

Run from the repository root:

```sh
python3 experiments/ema-grid-search/run.py
python3 experiments/ema-grid-search/coverage.py
```

To complete the hourly cache from MOEX ISS before rerunning the sweep:

```sh
python3 experiments/ema-grid-search/fetch_hourly.py --workers 8
python3 experiments/ema-grid-search/run.py
```

For a validation subset:

```sh
python3 experiments/ema-grid-search/run.py --symbols PLZL VTBR --timeframes 1D 1H --out /tmp/ema-grid-validation
```

Outputs are deliberately outside Git: `results/manifest.json` records the assumptions, `results/progress.csv` records each series or missing cache, `results/fetch_hourly_progress.csv` records download failures, and `results/<timeframe>/<ticker>.csv.gz` contains **every pair and mode**, including losses. The script resumes completed series. `run.log` and `fetch_hourly.log` give live lines when run with redirected output. A `missing_cache` row means the ticker/timeframe was **not tested**; a later `complete` row supersedes it after a rerun. OOS columns start at 2025-01-01, but because the previous research already inspected that period, it is not a pristine independent holdout. None of the rows alone establish a profitable strategy.

The first selection step should look for broad neighborhoods of positive, cost-adjusted results with enough closed trades and acceptable drawdown, then compare fixed parameter choices on new data and reconcile finalists with TradingView. Ranking by maximum historical return alone would favor chance winners among roughly 20,000 comparisons per ticker/timeframe/direction.

To watch an active run from another terminal, use `tail -f experiments/ema-grid-search/run.log` for the parameter sweep or `tail -f experiments/ema-grid-search/fetch_hourly.log` for MOEX downloads. `python3 experiments/ema-grid-search/coverage.py` prints current completed/missing/failed/pending ticker counts without reading millions of strategy rows.
