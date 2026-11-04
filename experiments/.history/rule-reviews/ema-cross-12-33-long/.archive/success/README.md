# EMA 12/33 — кандидаты по рынку РФ

По состоянию на 31.10.2026: 505 активных инструментов TQBR на 1D/1W/1M; 1H/4H проверены для 50 наиболее оборотных. Все 45 пар из периодов 6, 12, 33, 66, 111, 222, 333, 444, 555, 666 проверены в режимах long, short, long+short. Это **общий архив скана**, поэтому отдельная строка здесь не является результатом именно [фиксированного EMA12/33 long-only Pine](../../strategy.pine): сверяйте пару, направление и таймфрейм.

`success` означает прохождение **заданного фильтра в историческом тесте**, не гарантию будущего дохода. Для short не учтены заём бумаги, дивидендные выплаты по короткой позиции и доступность шорта у брокера. 4H построен из последовательных часовых свечей MOEX и может отличаться от 4H TradingView.

Строк по режимам: long 38, short 77, long+short 78. Полный перечень: [candidates.csv](candidates.csv).

| Тикер | Интервал | Режим | Закрытых сделок | Прибыльных | Доходность | Просадка | Доходность 2025–26 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| [PLZL](PLZL/README.md) | 1H | long | 176 | 68/176 (38.64%) | 24.96% | -6.19% | 16.52% |
| [SMLT](SMLT/README.md) | 1H | long | 168 | 42/168 (25.0%) | 7.58% | -9.92% | 15.86% |
| [VKCO](VKCO/README.md) | 1D | long | 13 | 5/13 (38.46%) | 11.49% | -14.83% | 13.27% |
| [NVTK](NVTK/README.md) | 1H | long | 170 | 55/170 (32.35%) | 15.53% | -5.22% | 12.29% |
| [POSI](POSI/README.md) | 1D | long | 10 | 5/10 (50.0%) | 38.47% | -8.04% | 11.53% |
| [GAZP](GAZP/README.md) | 1H | long | 168 | 49/168 (29.17%) | 19.15% | -6.5% | 10.22% |
| [PLZL](PLZL/README.md) | 1D | long | 14 | 5/14 (35.71%) | 22.37% | -7.46% | 9.79% |
| [SELG](SELG/README.md) | 1D | long | 13 | 6/13 (46.15%) | 18.61% | -8.91% | 8.81% |
| [AFKS](AFKS/README.md) | 1H | long | 162 | 53/162 (32.72%) | 18.57% | -9.03% | 8.64% |
| [X5](X5/README.md) | 4H | long | 28 | 11/28 (39.29%) | 8.45% | -4.06% | 8.45% |
| [OZON](OZON/README.md) | 4H | long | 41 | 12/41 (29.27%) | 23.09% | -7.14% | 7.26% |
| [T](T/README.md) | 1H | long | 171 | 52/171 (30.41%) | 8.2% | -5.62% | 7.15% |
| [IRAO](IRAO/README.md) | 4H | long | 46 | 16/46 (34.78%) | 5.6% | -5.7% | 6.92% |
| [VTBR](VTBR/README.md) | 1H | long | 178 | 55/178 (30.9%) | 5.04% | -6.42% | 6.64% |
| [LKOH](LKOH/README.md) | 1H | long | 181 | 58/181 (32.04%) | 9.62% | -6.73% | 6.59% |
| [VTBR](VTBR/README.md) | 1D | long | 15 | 6/15 (40.0%) | 5.77% | -9.18% | 6.52% |
| [OZON](OZON/README.md) | 1H | long | 166 | 49/166 (29.52%) | 21.38% | -10.54% | 5.5% |
| [T](T/README.md) | 4H | long | 49 | 15/49 (30.61%) | 0.61% | -8.1% | 4.79% |
| [SIBN](SIBN/README.md) | 1D | long | 12 | 3/12 (25.0%) | 22.67% | -8.45% | 4.6% |
| [VTBR](VTBR/README.md) | 4H | long | 46 | 11/46 (23.91%) | 3.21% | -8.46% | 4.2% |
| [RNFT](RNFT/README.md) | 1D | long | 15 | 5/15 (33.33%) | 13.41% | -14.5% | 3.74% |
| [TATN](TATN/README.md) | 1H | long | 173 | 54/173 (31.21%) | 6.16% | -7.64% | 3.46% |
| [X5](X5/README.md) | 1H | long | 128 | 38/128 (29.69%) | 3.22% | -6.88% | 3.22% |
| [ROSN](ROSN/README.md) | 4H | long | 46 | 13/46 (28.26%) | 5.57% | -7.48% | 3.12% |
| [PLZL](PLZL/README.md) | 4H | long | 48 | 17/48 (35.42%) | 14.83% | -9.28% | 3.09% |
| [PHOR](PHOR/README.md) | 4H | long | 50 | 12/50 (24.0%) | 3.0% | -6.3% | 2.74% |
| [POSI](POSI/README.md) | 1H | long | 186 | 53/186 (28.49%) | 0.64% | -12.68% | 2.43% |
| [MTSS](MTSS/README.md) | 4H | long | 48 | 15/48 (31.25%) | 8.57% | -4.63% | 2.42% |
| [TATN](TATN/README.md) | 1D | long | 13 | 4/13 (30.77%) | 22.92% | -7.65% | 2.29% |
| [CBOM](CBOM/README.md) | 1D | long | 16 | 7/16 (43.75%) | 15.66% | -14.12% | 2.26% |
| [TATN](TATN/README.md) | 4H | long | 49 | 17/49 (34.69%) | 5.82% | -8.63% | 2.12% |
| [UPRO](UPRO/README.md) | 4H | long | 45 | 9/45 (20.0%) | 9.99% | -10.7% | 1.97% |
| [MOEX](MOEX/README.md) | 4H | long | 51 | 19/51 (37.25%) | 6.89% | -5.47% | 1.78% |
| [TRNFP](TRNFP/README.md) | 1D | long | 15 | 6/15 (40.0%) | 7.88% | -7.52% | 0.56% |
| [AFKS](AFKS/README.md) | 1D | long | 15 | 4/15 (26.67%) | 14.34% | -10.39% | 0.48% |
| [ROSN](ROSN/README.md) | 1H | long | 183 | 50/183 (27.32%) | 4.08% | -7.93% | 0.46% |
| [AFKS](AFKS/README.md) | 4H | long | 45 | 15/45 (33.33%) | 7.19% | -9.72% | 0.26% |
| [ASTR](ASTR/README.md) | 1H | long | 177 | 49/177 (27.68%) | 2.29% | -14.11% | 0.21% |
| [SMLT](SMLT/README.md) | 1H | long_short | 337 | 109/337 (32.34%) | 97.48% | -10.99% | 69.3% |
| [PLZL](PLZL/README.md) | 1H | long_short | 352 | 123/352 (34.94%) | 46.35% | -6.55% | 37.73% |
| [VKCO](VKCO/README.md) | 1D | long_short | 26 | 11/26 (42.31%) | 31.53% | -25.32% | 34.83% |
| [POSI](POSI/README.md) | 1D | long_short | 20 | 12/20 (60.0%) | 66.25% | -12.05% | 33.8% |
| [AFKS](AFKS/README.md) | 1H | long_short | 325 | 112/325 (34.46%) | 55.9% | -7.49% | 31.54% |
| [SPBE](SPBE/README.md) | 4H | long_short | 89 | 35/89 (39.33%) | 90.54% | -14.92% | 25.82% |
| [VKCO](VKCO/README.md) | 4H | long_short | 93 | 33/93 (35.48%) | 37.52% | -9.2% | 24.6% |
| [OZON](OZON/README.md) | 1D | long_short | 26 | 10/26 (38.46%) | 53.21% | -11.74% | 24.36% |
| [X5](X5/README.md) | 4H | long_short | 57 | 23/57 (40.35%) | 24.35% | -4.4% | 24.35% |
| [SMLT](SMLT/README.md) | 4H | long_short | 94 | 35/94 (37.23%) | 56.21% | -10.54% | 24.04% |
| [HYDR](HYDR/README.md) | 1D | long_short | 27 | 10/27 (37.04%) | 16.13% | -14.48% | 23.02% |
| [PLZL](PLZL/README.md) | 1D | long_short | 29 | 10/29 (34.48%) | 25.13% | -14.2% | 22.47% |
| [GAZP](GAZP/README.md) | 1H | long_short | 337 | 105/337 (31.16%) | 47.36% | -5.72% | 21.0% |
| [UPRO](UPRO/README.md) | 4H | long_short | 91 | 26/91 (28.57%) | 31.5% | -8.23% | 20.32% |
| [IRAO](IRAO/README.md) | 4H | long_short | 93 | 35/93 (37.63%) | 18.89% | -5.58% | 19.8% |
| [VTBR](VTBR/README.md) | 1D | long_short | 30 | 10/30 (33.33%) | 17.48% | -15.03% | 19.1% |
| [PLZL](PLZL/README.md) | 4H | long_short | 96 | 30/96 (31.25%) | 25.01% | -8.9% | 17.86% |
| [FEES](FEES/README.md) | 1D | long_short | 30 | 11/30 (36.67%) | 18.87% | -9.96% | 17.74% |
| [VTBR](VTBR/README.md) | 1H | long_short | 356 | 113/356 (31.74%) | 25.8% | -9.61% | 17.7% |
| [ALRS](ALRS/README.md) | 4H | long_short | 78 | 32/78 (41.03%) | 28.61% | -7.88% | 17.14% |
| [NVTK](NVTK/README.md) | 1H | long_short | 341 | 114/341 (33.43%) | 35.67% | -6.11% | 16.81% |
| [ALRS](ALRS/README.md) | 1H | long_short | 360 | 117/360 (32.5%) | 36.33% | -9.79% | 16.33% |

## Отдельно: ≥50% прибыльных закрытых сделок

Этот показатель не является главным критерием прибыльности; он показывает частоту выигрышных сделок. Полная таблица содержит и стратегии с win rate ниже 50%, но положительным итогом.

| Тикер | Интервал | Режим | Прибыльных / всего | Доходность |
| --- | --- | --- | ---: | ---: |
| [POSI](POSI/README.md) | 1D | long | 5/10 (50.0%) | 38.47% |
| [POSI](POSI/README.md) | 1D | long_short | 12/20 (60.0%) | 66.25% |
| [SELG](SELG/README.md) | 1D | long_short | 13/26 (50.0%) | 37.48% |
| [SELG](SELG/README.md) | 1D | short | 7/13 (53.85%) | 15.92% |
| [SIBN](SIBN/README.md) | 1D | short | 6/12 (50.0%) | 7.34% |

## Источники и полные данные

- [Все тикеры с отдельным README](../../../../legacy-ema/12-33-cross/execute/research/tickers)
- [Все проверки 1D/1W/1M](../../../../legacy-ema/12-33-cross/execute/research/daily_weekly_monthly/all_results.csv)
- [Все проверки 1H/4H](../../../../legacy-ema/12-33-cross/execute/research/intraday/all_results.csv)
- [Сравнение 45 пар EMA](../../../../legacy-ema/12-33-cross/execute/research/PAIR_COMPARISON.md)
- [Стресс по затратам](COST_STRESS.md)
- [Повторяемость по годам](../../../../legacy-ema/12-33-cross/execute/research/PATTERNS.md)
- [Скриншот TradingView LKOH](../../../../legacy-ema/12-33-cross/execute/evidence/LKOH_tradingview_2026-10-31.png)

Базовая стратегия [12/33](../../strategy.pine); [скрипт сравнения направлений и пар](../../../../legacy-ema/12-33-cross/execute/variants.pine).
