# Проверка чувствительности к затратам

Для всех строк из `success` повторён период 2025–2026 с дополнительным проскальзыванием 0,10% на сторону и суммарным проскальзыванием 3 тика вместо 1. Комиссия остаётся 0,05% на сторону. Это стресс-сценарий, а не прогноз фактического исполнения.

Long-кандидатов: 38; с положительной доходностью после стресса: 24. Short и long+short в CSV присутствуют, но стоимость займа и выплаты дивидендов по короткой позиции всё ещё не учтены.

| Тикер | Интервал | База 2025–26 | Стресс 2025–26 |
| --- | --- | ---: | ---: |
| [VKCO](VKCO/README.md) | 1D | 13.27% | 12.91% |
| [POSI](POSI/README.md) | 1D | 11.53% | 11.24% |
| [PLZL](PLZL/README.md) | 1D | 9.79% | 9.35% |
| [SELG](SELG/README.md) | 1D | 8.81% | 8.37% |
| [PLZL](PLZL/README.md) | 1H | 16.52% | 8.32% |
| [X5](X5/README.md) | 4H | 8.45% | 6.3% |
| [VTBR](VTBR/README.md) | 1D | 6.52% | 6.18% |
| [SMLT](SMLT/README.md) | 1H | 15.86% | 5.55% |
| [OZON](OZON/README.md) | 4H | 7.26% | 5.17% |
| [IRAO](IRAO/README.md) | 4H | 6.92% | 4.64% |
| [NVTK](NVTK/README.md) | 1H | 12.29% | 4.44% |
| [SIBN](SIBN/README.md) | 1D | 4.6% | 4.19% |
| [RNFT](RNFT/README.md) | 1D | 3.74% | 3.01% |
| [T](T/README.md) | 4H | 4.79% | 2.93% |
| [GAZP](GAZP/README.md) | 1H | 10.22% | 2.41% |
| [VTBR](VTBR/README.md) | 4H | 4.2% | 2.24% |
| [TATN](TATN/README.md) | 1D | 2.29% | 1.92% |
| [CBOM](CBOM/README.md) | 1D | 2.26% | 1.84% |
| [AFKS](AFKS/README.md) | 1H | 8.64% | 1.52% |
| [PLZL](PLZL/README.md) | 4H | 3.09% | 1.15% |
| [ROSN](ROSN/README.md) | 4H | 3.12% | 0.87% |
| [PHOR](PHOR/README.md) | 4H | 2.74% | 0.54% |
| [T](T/README.md) | 1H | 7.15% | 0.09% |
| [TRNFP](TRNFP/README.md) | 1D | 0.56% | 0.06% |

[Все результаты стресса](cost_stress.csv).
