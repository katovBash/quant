# Итог эксперимента



Снимок свечей: MOEX ISS local snapshot 2026-10-30. Месячный расчёт: непрерывный счёт с переоценкой открытых позиций. Модель расходов: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`.

Корпоративные события: покрытие неполное или выплаты не применены; результат REVIEW_ONLY. Исторические проценты без учтённых выплат нельзя считать полной доходностью акций.

Покрытие: 426 акций, 1D, 1H, 4H; 2856 пар «акция × интервал × вариант». Ошибок расчёта: 0.

## Что видно по всей выборке

Вариантов с дополнительным правилом: 1904. Из 1904 сопоставимых с контролем вариантов у 109 одновременно больше прибыльных месяцев, мягче худший месяц и выше PnL за последний сопоставимый календарный год или YTD. Это сравнение на просмотренной истории, без автоматического допуска.

| Интервал и правило | Пар | Медиана прибыльных месяцев | Средний месяц по парам |
|---|---:|---:|---:|
| 1D · Контроль | 426 | 39.4% | -1 349 ₽ · -0.13% |
| 1D · Остальные варианты | 852 | 12.1% | 243 ₽ · +0.02% |
| 1H · Контроль | 263 | 42.4% | -2 514 ₽ · -0.25% |
| 1H · Остальные варианты | 526 | 27.3% | -2 707 ₽ · -0.28% |
| 4H · Контроль | 263 | 40.0% | -2 730 ₽ · -0.27% |
| 4H · Остальные варианты | 526 | 27.3% | -6 ₽ · -0.00% |



## Примеры для ручного разбора

Сортировка: число прибыльных месяцев, затем худший месячный PnL. Соседние настройки и контроль нужно сравнить перед выводом.

| Акция · интервал · вариант | Плюс / все месяцы | Средний месяц | Средний прибыльный / убыточный месяц | Худший месяц | Последний календарный год / YTD | Контроль: плюс / месяцы |
|---|---:|---:|---:|---:|---:|---:|
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 22 / 33 | 4 089 ₽ · +0.40% | 14 575 ₽ / -16 882 ₽ | -49 399 ₽ | 2026 YTD: 11 018 ₽ · +0.98% | 12 / 33 |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 21 / 33 | 3 649 ₽ · +0.36% | 11 981 ₽ / -10 932 ₽ | -31 345 ₽ | 2026 YTD: 25 768 ₽ · +2.35% | 15 / 33 |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 18 / 33 | 7 206 ₽ · +0.66% | 17 216 ₽ / -6 553 ₽ | -15 363 ₽ | 2026 YTD: 39 357 ₽ · +3.28% | 11 / 33 |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 18 / 33 | 9 958 ₽ · +0.90% | 24 313 ₽ / -9 911 ₽ | -19 514 ₽ | 2026 YTD: 124 426 ₽ · +10.33% | 11 / 33 |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 18 / 33 | 6 525 ₽ · +0.62% | 19 608 ₽ / -9 175 ₽ | -24 769 ₽ | 2026 YTD: 107 343 ₽ · +9.69% | 15 / 33 |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 17 / 33 | 1 054 ₽ · +0.11% | 11 399 ₽ / -9 936 ₽ | -29 814 ₽ | 2026 YTD: -44 695 ₽ · -4.14% | 12 / 33 |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 17 / 33 | -1 232 ₽ · -0.12% | 9 240 ₽ / -12 357 ₽ | -34 883 ₽ | 2026 YTD: -22 762 ₽ · -2.32% | 11 / 33 |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 17 / 33 | 6 769 ₽ · +0.63% | 20 377 ₽ / -20 509 ₽ | -43 003 ₽ | 2026 YTD: 75 381 ₽ · +6.57% | 14 / 33 |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 17 / 33 | 1 947 ₽ · +0.20% | 15 153 ₽ / -12 084 ₽ | -47 506 ₽ | 2026 YTD: 23 606 ₽ · +2.27% | 12 / 33 |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 17 / 33 | 1 616 ₽ · +0.18% | 16 551 ₽ / -17 542 ₽ | -49 903 ₽ | 2026 YTD: -36 528 ₽ · -3.35% | 12 / 33 |

## PnL по календарным годам

Результат считается по одному непрерывному счёту: капитал на конец года минус капитал на начало года. Доходность года делится на капитал в его начале, а не складывается из месячных процентов. Неполный год обозначен явно; учитываются только завершённые месяцы.

| Акция · интервал · вариант | Год | Полных месяцев | PnL | Доходность |
|---|---|---:|---:|---:|
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 2024 | 12 | 24 876 ₽ | +2.49% |
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 2025 | 12 | 99 057 ₽ | +9.67% |
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 2026 · 01–09 (неполный) | 9 | 11 018 ₽ | +0.98% |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 2024 | 12 | 51 484 ₽ | +5.15% |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 2025 | 12 | 43 153 ₽ | +4.10% |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | 25 768 ₽ | +2.35% |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 2024 | 12 | 34 700 ₽ | +3.47% |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 2025 | 12 | 163 749 ₽ | +15.83% |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | 39 357 ₽ | +3.28% |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 2024 | 12 | 48 183 ₽ | +4.82% |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 2025 | 12 | 155 996 ₽ | +14.88% |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | 124 426 ₽ | +10.33% |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 2024 | 12 | 154 079 ₽ | +15.41% |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 2025 | 12 | -46 098 ₽ | -3.99% |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 2026 · 01–09 (неполный) | 9 | 107 343 ₽ | +9.69% |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 2024 | 12 | 117 693 ₽ | +11.77% |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 2025 | 12 | -38 204 ₽ | -3.42% |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | -44 695 ₽ | -4.14% |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 2024 | 12 | 23 787 ₽ | +2.38% |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 2025 | 12 | -41 672 ₽ | -4.07% |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | -22 762 ₽ | -2.32% |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 2024 | 12 | 131 526 ₽ | +13.15% |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 2025 | 12 | 16 456 ₽ | +1.45% |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 2026 · 01–09 (неполный) | 9 | 75 381 ₽ | +6.57% |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 2024 | 12 | 41 241 ₽ | +4.12% |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 2025 | 12 | -589 ₽ | -0.06% |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | 23 606 ₽ | +2.27% |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 2024 | 12 | -8 380 ₽ | -0.84% |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 2025 | 12 | 98 232 ₽ | +9.91% |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 2026 · 01–09 (неполный) | 9 | -36 528 ₽ | -3.35% |

## Средний доход за месяц на последних отрезках

Только полные последовательные календарные месяцы. Каждая ячейка — средний PnL **за один месяц** в указанном отрезке и средняя месячная доходность; «—» означает, что полного отрезка нет. Все пары и точные значения есть в [monthly_case_summary.csv](monthly_case_summary.csv).

| Акция · интервал · вариант | Последний 1 месяц | Последние 3 месяца | Последние 6 месяцев | Последние 9 месяцев | Последние 12 месяцев |
|---|---:|---:|---:|---:|---:|
| WUSH · 1H · `bollinger-squeeze-breakout_20` | -13 122 ₽ · -1.14% | 5 148 ₽ · +0.58% | 4 798 ₽ · +0.50% | 1 224 ₽ · +0.16% | 4 428 ₽ · +0.44% |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 1 647 ₽ · +0.15% | 11 077 ₽ · +1.01% | 8 005 ₽ · +0.74% | 2 863 ₽ · +0.26% | 885 ₽ · +0.08% |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 4 291 ₽ · +0.35% | 6 038 ₽ · +0.49% | 6 614 ₽ · +0.55% | 4 373 ₽ · +0.36% | 3 976 ₽ · +0.33% |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 20 930 ₽ · +1.60% | 495 ₽ · +0.04% | 12 504 ₽ · +0.98% | 13 825 ₽ · +1.11% | 21 210 ₽ · +1.85% |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 4 694 ₽ · +0.39% | -2 249 ₽ · -0.18% | 12 954 ₽ · +1.12% | 11 927 ₽ · +1.04% | 10 772 ₽ · +0.95% |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | -12 251 ₽ · -1.17% | 3 985 ₽ · +0.39% | -3 386 ₽ · -0.32% | -4 966 ₽ · -0.46% | -5 855 ₽ · -0.54% |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 6 802 ₽ · +0.71% | 15 643 ₽ · +1.70% | 2 294 ₽ · +0.26% | -2 529 ₽ · -0.24% | -2 460 ₽ · -0.24% |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 0 ₽ · +0.00% | 5 075 ₽ · +0.42% | 12 563 ₽ · +1.08% | 8 376 ₽ · +0.72% | 6 375 ₽ · +0.55% |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | -14 055 ₽ · -1.30% | -19 260 ₽ · -1.75% | -443 ₽ · -0.01% | 2 623 ₽ · +0.27% | -679 ₽ · -0.05% |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 1 641 ₽ · +0.16% | -3 698 ₽ · -0.35% | -7 145 ₽ · -0.64% | -4 059 ₽ · -0.36% | -3 106 ₽ · -0.28% |

## Каждый полный месяц

Для десяти примеров выше показана доходность **каждого отдельного месяца**, а не накопленная доходность за окно. 🟩 — прибыль, 🟥 — убыток, ⬜ — ноль; «—» означает отсутствие полного месяца. Все пары и месяцы, включая не вошедшие в примеры, сохранены в [monthly_returns.csv](monthly_returns.csv).

| Акция · интервал · вариант | Год | Янв | Фев | Мар | Апр | Май | Июн | Июл | Авг | Сен | Окт | Ноя | Дек |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 2024 | 🟩 +0.13% | 🟩 +0.02% | 🟩 +2.08% | 🟩 +1.49% | 🟥 -0.88% | 🟥 -1.55% | 🟥 -0.67% | 🟩 +0.26% | 🟩 +0.74% | 🟩 +0.22% | 🟥 -0.77% | 🟩 +1.45% |
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 2025 | 🟩 +0.08% | 🟩 +1.65% | 🟩 +0.91% | 🟥 -2.14% | 🟩 +2.00% | 🟥 -1.11% | 🟩 +1.54% | 🟩 +1.86% | 🟩 +0.72% | 🟩 +3.24% | 🟩 +0.46% | 🟩 +0.17% |
| WUSH · 1H · `bollinger-squeeze-breakout_20` | 2026 | 🟩 +1.27% | 🟥 -1.15% | 🟥 -1.69% | 🟩 +0.07% | 🟩 +2.69% | 🟥 -1.52% | 🟥 -4.41% | 🟩 +7.29% | 🟥 -1.14% | — | — | — |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 2024 | 🟥 -0.91% | 🟥 -0.27% | 🟩 +1.38% | 🟩 +1.32% | 🟩 +3.48% | 🟥 -2.67% | 🟩 +2.36% | 🟩 +0.15% | 🟥 -1.21% | 🟩 +0.40% | 🟥 -3.02% | 🟩 +4.30% |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 2025 | 🟥 -0.18% | 🟩 +1.28% | 🟩 +0.28% | 🟩 +0.21% | 🟩 +0.73% | 🟥 -0.37% | 🟩 +1.89% | 🟩 +1.16% | 🟩 +0.44% | 🟩 +0.37% | 🟥 -0.22% | 🟥 -1.51% |
| AFKS · 1H · `bollinger-squeeze-breakout_30` | 2026 | 🟥 -0.56% | 🟥 -1.05% | 🟥 -0.43% | 🟩 +0.33% | 🟩 +0.59% | 🟩 +0.46% | 🟩 +0.34% | 🟩 +2.56% | 🟩 +0.15% | — | — | — |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 2024 | ⬜ +0.00% | 🟩 +1.03% | 🟥 -0.34% | ⬜ +0.00% | 🟩 +1.52% | ⬜ +0.00% | 🟩 +1.92% | 🟩 +0.18% | 🟥 -0.46% | 🟥 -0.90% | 🟩 +0.26% | 🟩 +0.26% |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 2025 | 🟩 +4.50% | 🟩 +7.19% | 🟥 -1.33% | 🟩 +0.31% | 🟥 -0.99% | 🟥 -0.53% | 🟥 -0.64% | 🟩 +4.77% | 🟩 +1.19% | 🟩 +0.56% | 🟩 +0.48% | 🟥 -0.34% |
| VSMO · 4H · `bollinger-squeeze-breakout_30` | 2026 | ⬜ +0.00% | 🟩 +0.24% | 🟥 -0.26% | 🟩 +2.11% | 🟩 +0.12% | 🟥 -0.42% | 🟥 -0.16% | 🟩 +1.30% | 🟩 +0.35% | — | — | — |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 2024 | ⬜ +0.00% | 🟩 +0.30% | 🟩 +1.30% | 🟥 -1.39% | 🟩 +0.42% | 🟩 +1.16% | 🟥 -0.44% | 🟩 +1.63% | 🟥 -1.89% | 🟥 -0.14% | 🟩 +5.35% | 🟥 -1.38% |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 2025 | ⬜ +0.00% | 🟥 -0.88% | 🟩 +0.05% | 🟩 +0.66% | 🟥 -0.94% | 🟩 +4.18% | 🟩 +0.33% | 🟥 -0.87% | ⬜ +0.00% | ⬜ +0.00% | 🟥 -0.64% | 🟩 +12.84% |
| KROT · 1D · `bollinger-squeeze-breakout_30` | 2026 | 🟩 +0.53% | 🟩 +0.65% | 🟩 +2.88% | 🟩 +2.04% | 🟩 +1.49% | 🟩 +2.23% | 🟥 -0.49% | 🟥 -0.98% | 🟩 +1.60% | — | — | — |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 2024 | 🟩 +10.50% | 🟥 -0.71% | 🟥 -0.34% | 🟥 -0.01% | 🟩 +1.06% | 🟩 +0.08% | 🟩 +1.30% | 🟩 +0.31% | 🟩 +0.48% | 🟥 -1.30% | 🟩 +4.11% | 🟥 -0.53% |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 2025 | 🟥 -2.15% | 🟩 +0.13% | 🟥 -1.02% | 🟥 -0.50% | 🟩 +0.63% | 🟥 -0.70% | 🟥 -1.16% | 🟩 +0.05% | 🟥 -1.32% | 🟩 +0.55% | 🟩 +2.92% | 🟥 -1.42% |
| SFIN · 1H · `bollinger-squeeze-breakout_20` | 2026 | 🟩 +0.29% | 🟥 -0.06% | 🟩 +2.43% | 🟩 +2.12% | 🟩 +4.26% | 🟩 +0.90% | 🟥 -0.35% | 🟥 -0.59% | 🟩 +0.39% | — | — | — |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 2024 | 🟩 +1.12% | 🟩 +0.49% | 🟩 +0.74% | 🟥 -0.38% | 🟩 +1.59% | 🟩 +0.10% | 🟥 -0.13% | 🟩 +0.52% | 🟩 +1.40% | 🟩 +3.63% | 🟩 +1.02% | 🟩 +1.13% |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 2025 | 🟥 -1.59% | 🟥 -0.24% | 🟩 +0.43% | 🟩 +0.98% | 🟥 -2.68% | 🟩 +0.45% | 🟩 +1.45% | 🟩 +0.95% | 🟥 -0.81% | 🟥 -0.19% | 🟥 -1.48% | 🟥 -0.66% |
| RTKM · 1H · `bollinger-squeeze-breakout_30` | 2026 | 🟥 -1.56% | 🟥 -0.37% | 🟥 -0.34% | 🟥 -0.42% | 🟥 -0.97% | 🟥 -1.70% | 🟩 +1.59% | 🟩 +0.76% | 🟥 -1.17% | — | — | — |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 2024 | 🟩 +1.00% | 🟥 -1.37% | 🟥 -0.94% | 🟩 +1.05% | 🟩 +0.41% | 🟥 -1.23% | 🟩 +0.07% | 🟥 -1.86% | 🟥 -0.48% | 🟩 +2.40% | 🟩 +1.59% | 🟩 +1.82% |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 2025 | 🟥 -1.73% | 🟥 -0.77% | 🟩 +0.19% | 🟥 -2.22% | 🟥 -0.09% | 🟩 +1.40% | 🟥 -0.26% | 🟥 -0.02% | 🟩 +0.08% | 🟩 +0.24% | 🟥 -1.66% | 🟩 +0.75% |
| MTLR · 1H · `bollinger-squeeze-breakout_30` | 2026 | 🟥 -0.88% | 🟥 -1.47% | 🟥 -1.42% | 🟩 +0.15% | 🟩 +0.03% | 🟥 -3.68% | 🟩 +3.70% | 🟩 +0.67% | 🟩 +0.71% | — | — | — |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 2024 | 🟩 +1.48% | 🟩 +2.93% | 🟩 +3.45% | 🟩 +1.28% | ⬜ +0.00% | ⬜ +0.00% | ⬜ +0.00% | 🟩 +4.78% | 🟥 -3.75% | 🟩 +1.35% | 🟥 -1.65% | 🟩 +2.85% |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 2025 | 🟥 -1.27% | 🟥 -1.56% | 🟩 +0.48% | 🟩 +2.74% | 🟩 +0.09% | 🟥 -1.81% | 🟩 +0.21% | 🟩 +0.03% | 🟩 +2.54% | 🟩 +0.72% | 🟩 +0.17% | 🟥 -0.79% |
| BANE · 1D · `bollinger-squeeze-breakout_20` | 2026 | ⬜ +0.00% | ⬜ +0.00% | ⬜ +0.00% | ⬜ +0.00% | ⬜ +0.00% | 🟩 +5.24% | 🟩 +1.26% | ⬜ +0.00% | ⬜ +0.00% | — | — | — |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 2024 | 🟥 -0.55% | 🟥 -0.88% | 🟩 +0.90% | 🟥 -0.06% | 🟩 +1.85% | 🟥 -0.35% | 🟩 +0.06% | 🟥 -0.47% | 🟩 +1.43% | 🟥 -1.55% | 🟩 +2.06% | 🟩 +1.69% |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 2025 | 🟩 +0.76% | 🟩 +1.51% | 🟩 +2.05% | 🟥 -4.37% | 🟩 +2.03% | 🟩 +0.40% | 🟩 +1.60% | 🟥 -0.35% | 🟥 -0.51% | 🟥 -0.73% | 🟥 -1.21% | 🟥 -1.04% |
| ROLO · 1H · `bollinger-squeeze-breakout_30` | 2026 | 🟩 +1.37% | 🟩 +0.55% | 🟩 +0.59% | 🟥 -0.75% | 🟩 +1.06% | 🟩 +4.85% | 🟥 -2.48% | 🟥 -1.46% | 🟥 -1.30% | — | — | — |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 2024 | 🟩 +0.95% | 🟩 +0.88% | 🟩 +2.97% | 🟥 -0.51% | ⬜ +0.00% | 🟩 +0.83% | 🟥 -2.11% | 🟥 -4.85% | 🟩 +0.17% | ⬜ +0.00% | 🟩 +0.88% | 🟩 +0.16% |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 2025 | 🟩 +9.23% | 🟥 -0.63% | 🟩 +1.29% | 🟩 +1.87% | 🟥 -2.81% | ⬜ +0.00% | 🟩 +0.67% | 🟩 +2.66% | 🟥 -2.25% | 🟩 +0.35% | 🟥 -0.15% | 🟥 -0.27% |
| RTSBP · 1H · `bollinger-squeeze-breakout_30` | 2026 | 🟩 +0.30% | 🟥 -1.06% | 🟩 +1.36% | 🟥 -4.05% | 🟥 -1.34% | 🟩 +2.58% | 🟥 -0.21% | 🟥 -0.99% | 🟩 +0.16% | — | — | — |

## Как читать результат

Все пары, включая убыточные и правила с несколькими удачными месяцами, есть в [таблице пар](monthly_case_summary.csv). Исходные [месяцы](monthly_returns.csv) и [разбивка по фазам](monthly_regime_profiles.csv) сохранены отдельно. Если фазы рынка размечены после завершения месяца, их нельзя использовать как сигнал того же месяца.

Неполный последний месяц не включён в годовой итог. Доходность одной пары не равна доходности общего портфеля. Если модель расходов `gross_before_costs`, результат до комиссии, спреда, проскальзывания, дивидендов и стоимости short. История уже просмотрена при выборе гипотезы; статус `REVIEW_ONLY`.

## Long и short по отдельности

Доля удачных сделок считается **только по закрытым сделкам**. Доходность включает переоценку открытой позиции и потому не выводится из этой доли. Сравнение направлений проведено на уже просмотренной истории; это гипотеза для отдельной проверки.

| Акция · интервал · вариант | Режим | Закрыто long / выигрыш | Закрыто short / выигрыш | Плюсовые месяцы | Вывод |
|---|---|---:|---:|---:|---|
| MTLR · 4H · `bollinger-squeeze-breakout_30` | long_only | 4/12 · 33.3% | 0 · — | 6/33 | diagnostic_only; selected examples, not whole grid |
| MTLR · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 10/21 · 47.6% | 12/33 | diagnostic_only; selected examples, not whole grid |
| RTKM · 4H · `bollinger-squeeze-breakout_30` | long_only | 6/23 · 26.1% | 0 · — | 4/33 | diagnostic_only; selected examples, not whole grid |
| RTKM · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 11/18 · 61.1% | 12/33 | diagnostic_only; selected examples, not whole grid |
| RNFT · 4H · `bollinger-squeeze-breakout_30` | long_only | 8/17 · 47.1% | 0 · — | 9/33 | diagnostic_only; selected examples, not whole grid |
| RNFT · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 8/20 · 40.0% | 8/33 | diagnostic_only; selected examples, not whole grid |
| MSNG · 4H · `bollinger-squeeze-breakout_30` | long_only | 6/16 · 37.5% | 0 · — | 8/33 | diagnostic_only; selected examples, not whole grid |
| MSNG · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 8/18 · 44.4% | 7/33 | diagnostic_only; selected examples, not whole grid |
| BANEP · 4H · `bollinger-squeeze-breakout_30` | long_only | 8/16 · 50.0% | 0 · — | 11/33 | diagnostic_only; selected examples, not whole grid |
| BANEP · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 7/19 · 36.8% | 8/33 | diagnostic_only; selected examples, not whole grid |
| NLMK · 4H · `bollinger-squeeze-breakout_30` | long_only | 7/18 · 38.9% | 0 · — | 9/33 | diagnostic_only; selected examples, not whole grid |
| NLMK · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 9/19 · 47.4% | 9/33 | diagnostic_only; selected examples, not whole grid |
| T · 4H · `bollinger-squeeze-breakout_30` | long_only | 6/15 · 40.0% | 0 · — | 5/33 | diagnostic_only; selected examples, not whole grid |
| T · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 11/21 · 52.4% | 10/33 | diagnostic_only; selected examples, not whole grid |
| CHMF · 4H · `bollinger-squeeze-breakout_30` | long_only | 7/21 · 33.3% | 0 · — | 8/33 | diagnostic_only; selected examples, not whole grid |
| CHMF · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 8/18 · 44.4% | 9/33 | diagnostic_only; selected examples, not whole grid |
| WUSH · 4H · `bollinger-squeeze-breakout_30` | long_only | 3/16 · 18.8% | 0 · — | 4/33 | diagnostic_only; selected examples, not whole grid |
| WUSH · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 14/20 · 70.0% | 13/33 | diagnostic_only; selected examples, not whole grid |
| SPBE · 4H · `bollinger-squeeze-breakout_30` | long_only | 8/14 · 57.1% | 0 · — | 9/33 | diagnostic_only; selected examples, not whole grid |
| SPBE · 4H · `bollinger-squeeze-breakout_30` | short_only | 0 · — | 8/24 · 33.3% | 8/33 | diagnostic_only; selected examples, not whole grid |

[Все результаты по направлениям](trade_side_summary.csv). Если капитал уходит ниже нуля, вариант недопустим независимо от процента успешных сделок.

## Источник торговой идеи

Автор: John Bollinger. [Первоисточник](https://www.bollingerbands.com/tradestation-methods). Тип свидетельства: `mechanical_interpretation`.

Механическое правило этого теста: BandWidth reaches its trailing 20-bar low, then price closes outside a band; exit at middle band.

Полный личный журнал сделок не подтверждён; результаты выше относятся только к проверке сформулированной версии на локальных свечах.
