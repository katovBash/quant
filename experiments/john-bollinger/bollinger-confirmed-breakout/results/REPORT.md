# Итог эксперимента



Снимок свечей: MOEX ISS local snapshot 2026-10-30. Месячный расчёт: непрерывный счёт с переоценкой открытых позиций. Модель расходов: `after_30bps_round_trip_transaction_cost_equivalent; excludes dividends, short borrow and exchange lots`.

Корпоративные события: покрытие неполное или выплаты не применены; результат REVIEW_ONLY. Исторические проценты без учтённых выплат нельзя считать полной доходностью акций.

Покрытие: 426 акций, 1D, 1H, 4H; 2856 пар «акция × интервал × вариант». Ошибок расчёта: 0.

## Что видно по всей выборке

Вариантов с дополнительным правилом: 1904. Из 1904 сопоставимых с контролем вариантов у 341 одновременно больше прибыльных месяцев, мягче худший месяц и выше PnL за последний сопоставимый календарный год или YTD. Это сравнение на просмотренной истории, без автоматического допуска.

| Интервал и правило | Пар | Медиана прибыльных месяцев | Средний месяц по парам |
|---|---:|---:|---:|
| 1D · Контроль | 426 | 39.4% | -1 349 ₽ · -0.13% |
| 1D · Остальные варианты | 852 | 27.3% | 145 ₽ · +0.02% |
| 1H · Контроль | 263 | 42.4% | -2 514 ₽ · -0.25% |
| 1H · Остальные варианты | 526 | 33.3% | -3 219 ₽ · -0.35% |
| 4H · Контроль | 263 | 40.0% | -2 730 ₽ · -0.27% |
| 4H · Остальные варианты | 526 | 42.4% | 913 ₽ · +0.08% |



## Примеры для ручного разбора

Сортировка: число прибыльных месяцев, затем худший месячный PnL. Соседние настройки и контроль нужно сравнить перед выводом.

| Акция · интервал · вариант | Плюс / все месяцы | Средний месяц | Средний прибыльный / убыточный месяц | Худший месяц | Последний календарный год / YTD | Контроль: плюс / месяцы |
|---|---:|---:|---:|---:|---:|---:|
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 23 / 33 | 24 732 ₽ · +1.87% | 41 327 ₽ / -14 931 ₽ | -38 693 ₽ | 2026 YTD: 529 573 ₽ · +41.16% | 14 / 33 |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 22 / 33 | 5 219 ₽ · +0.49% | 11 676 ₽ / -7 696 ₽ | -13 439 ₽ | 2026 YTD: 62 621 ₽ · +5.64% | 15 / 33 |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 22 / 33 | 7 481 ₽ · +0.68% | 16 199 ₽ / -10 952 ₽ | -33 074 ₽ | 2026 YTD: 137 593 ₽ · +12.40% | 12 / 33 |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 22 / 33 | 19 696 ₽ · +1.61% | 40 938 ₽ / -22 787 ₽ | -46 128 ₽ | 2026 YTD: 461 434 ₽ · +38.82% | 15 / 33 |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 21 / 33 | 4 041 ₽ · +0.39% | 12 285 ₽ / -10 385 ₽ | -19 766 ₽ | 2026 YTD: 14 652 ₽ · +1.31% | 15 / 33 |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 21 / 32 | 8 390 ₽ · +0.76% | 16 044 ₽ / -9 780 ₽ | -23 031 ₽ | 2026 YTD: 62 000 ₽ · +5.14% | 9 / 32 |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 21 / 33 | 5 161 ₽ · +0.49% | 16 766 ₽ / -15 149 ₽ | -26 801 ₽ | 2026 YTD: 119 223 ₽ · +11.34% | 12 / 33 |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 21 / 33 | 6 438 ₽ · +0.60% | 17 495 ₽ / -12 912 ₽ | -29 974 ₽ | 2026 YTD: 129 786 ₽ · +11.99% | 9 / 33 |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 21 / 33 | 9 025 ₽ · +0.80% | 19 133 ₽ / -9 451 ₽ | -34 378 ₽ | 2026 YTD: 139 153 ₽ · +12.01% | 12 / 33 |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 21 / 33 | 9 246 ₽ · +0.83% | 21 597 ₽ / -13 492 ₽ | -47 402 ₽ | 2026 YTD: 151 859 ₽ · +13.17% | 11 / 33 |

## PnL по календарным годам

Результат считается по одному непрерывному счёту: капитал на конец года минус капитал на начало года. Доходность года делится на капитал в его начале, а не складывается из месячных процентов. Неполный год обозначен явно; учитываются только завершённые месяцы.

| Акция · интервал · вариант | Год | Полных месяцев | PnL | Доходность |
|---|---|---:|---:|---:|
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 2024 | 12 | 144 326 ₽ | +14.43% |
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 2025 | 12 | 142 244 ₽ | +12.43% |
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 2026 · 01–09 (неполный) | 9 | 529 573 ₽ | +41.16% |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 2024 | 12 | 78 652 ₽ | +7.87% |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 2025 | 12 | 30 949 ₽ | +2.87% |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 2026 · 01–09 (неполный) | 9 | 62 621 ₽ | +5.64% |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 2024 | 12 | 30 748 ₽ | +3.07% |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 2025 | 12 | 78 522 ₽ | +7.62% |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 2026 · 01–09 (неполный) | 9 | 137 593 ₽ | +12.40% |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 2024 | 12 | 195 091 ₽ | +19.51% |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 2025 | 12 | -6 549 ₽ | -0.55% |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 2026 · 01–09 (неполный) | 9 | 461 434 ₽ | +38.82% |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 2024 | 12 | 67 594 ₽ | +6.76% |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 2025 | 12 | 51 113 ₽ | +4.79% |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 2026 · 01–09 (неполный) | 9 | 14 652 ₽ | +1.31% |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 2024 · 02–12 (неполный) | 11 | 71 563 ₽ | +7.16% |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 2025 | 12 | 134 910 ₽ | +12.59% |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 2026 · 01–09 (неполный) | 9 | 62 000 ₽ | +5.14% |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 2024 | 12 | 23 823 ₽ | +2.38% |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 2025 | 12 | 27 254 ₽ | +2.66% |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 2026 · 01–09 (неполный) | 9 | 119 223 ₽ | +11.34% |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2024 | 12 | 145 545 ₽ | +14.55% |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2025 | 12 | -62 884 ₽ | -5.49% |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2026 · 01–09 (неполный) | 9 | 129 786 ₽ | +11.99% |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 2024 | 12 | 109 714 ₽ | +10.97% |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 2025 | 12 | 48 960 ₽ | +4.41% |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 2026 · 01–09 (неполный) | 9 | 139 153 ₽ | +12.01% |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 2024 | 12 | 73 619 ₽ | +7.36% |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 2025 | 12 | 79 654 ₽ | +7.42% |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 2026 · 01–09 (неполный) | 9 | 151 859 ₽ | +13.17% |

## Средний доход за месяц на последних отрезках

Только полные последовательные календарные месяцы. Каждая ячейка — средний PnL **за один месяц** в указанном отрезке и средняя месячная доходность; «—» означает, что полного отрезка нет. Все пары и точные значения есть в [monthly_case_summary.csv](monthly_case_summary.csv).

| Акция · интервал · вариант | Последний 1 месяц | Последние 3 месяца | Последние 6 месяцев | Последние 9 месяцев | Последние 12 месяцев |
|---|---:|---:|---:|---:|---:|
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 18 131 ₽ · +1.01% | 74 861 ₽ · +4.54% | 70 234 ₽ · +4.53% | 58 841 ₽ · +3.93% | 50 749 ₽ · +3.50% |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 33 014 ₽ · +2.90% | 15 251 ₽ · +1.34% | 7 061 ₽ · +0.62% | 6 958 ₽ · +0.62% | 5 115 ₽ · +0.46% |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 14 490 ₽ · +1.18% | 24 761 ₽ · +2.07% | 22 275 ₽ · +1.92% | 15 288 ₽ · +1.32% | 14 062 ₽ · +1.24% |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | -34 571 ₽ · -2.05% | 91 357 ₽ · +6.53% | 63 924 ₽ · +4.70% | 51 270 ₽ · +3.86% | 45 409 ₽ · +3.53% |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | -14 533 ₽ · -1.27% | 5 220 ₽ · +0.47% | 3 849 ₽ · +0.35% | 1 628 ₽ · +0.15% | 2 685 ₽ · +0.25% |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | -178 ₽ · -0.01% | -5 550 ₽ · -0.43% | 12 331 ₽ · +1.02% | 6 889 ₽ · +0.57% | 8 152 ₽ · +0.68% |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 18 702 ₽ · +1.62% | 20 768 ₽ · +1.89% | 18 899 ₽ · +1.74% | 13 247 ₽ · +1.23% | 5 114 ₽ · +0.48% |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2 965 ₽ · +0.25% | 20 411 ₽ · +1.75% | 21 210 ₽ · +1.88% | 14 421 ₽ · +1.28% | 8 803 ₽ · +0.78% |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 1 371 ₽ · +0.11% | 4 363 ₽ · +0.34% | 17 927 ₽ · +1.46% | 15 461 ₽ · +1.28% | 11 505 ₽ · +0.95% |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 14 220 ₽ · +1.10% | 36 546 ₽ · +2.98% | 26 113 ₽ · +2.17% | 16 873 ₽ · +1.40% | 11 207 ₽ · +0.93% |

## Каждый полный месяц

Для десяти примеров выше показана доходность **каждого отдельного месяца**, а не накопленная доходность за окно. 🟩 — прибыль, 🟥 — убыток, ⬜ — ноль; «—» означает отсутствие полного месяца. Все пары и месяцы, включая не вошедшие в примеры, сохранены в [monthly_returns.csv](monthly_returns.csv).

| Акция · интервал · вариант | Год | Янв | Фев | Мар | Апр | Май | Июн | Июл | Авг | Сен | Окт | Ноя | Дек |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 2024 | 🟩 +0.04% | 🟩 +10.86% | 🟩 +1.33% | 🟩 +0.85% | 🟩 +2.99% | 🟥 -1.67% | 🟥 -0.92% | 🟩 +1.00% | 🟥 -1.28% | 🟩 +1.86% | 🟩 +2.43% | 🟥 -3.27% |
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 2025 | ⬜ +0.00% | 🟩 +3.89% | 🟥 -0.69% | 🟩 +0.78% | 🟩 +0.41% | 🟥 -0.39% | 🟥 -0.04% | 🟥 -1.41% | 🟩 +2.93% | 🟥 -1.72% | 🟩 +5.45% | 🟩 +2.84% |
| SFIN · 4H · `bollinger-confirmed-breakout_20` | 2026 | 🟩 +5.51% | 🟩 +1.14% | 🟩 +1.59% | 🟩 +3.55% | 🟩 +6.97% | 🟩 +3.02% | 🟩 +8.59% | 🟩 +4.04% | 🟩 +1.01% | — | — | — |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 2024 | 🟩 +0.28% | 🟩 +0.22% | 🟩 +0.72% | 🟥 -0.24% | 🟩 +0.17% | 🟥 -0.92% | 🟩 +0.82% | 🟩 +1.54% | 🟩 +0.65% | 🟩 +2.59% | 🟥 -0.11% | 🟩 +1.92% |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 2025 | 🟥 -0.57% | 🟩 +1.24% | 🟩 +0.66% | 🟩 +1.16% | 🟥 -0.95% | 🟥 -1.04% | 🟩 +0.95% | 🟩 +0.08% | 🟩 +1.45% | 🟩 +1.32% | 🟥 -0.22% | 🟥 -1.20% |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | 2026 | 🟩 +2.40% | 🟥 -0.94% | 🟩 +0.38% | 🟩 +1.21% | 🟥 -0.43% | 🟥 -1.06% | 🟩 +1.10% | 🟩 +0.03% | 🟩 +2.90% | — | — | — |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 2024 | ⬜ +0.00% | 🟩 +0.07% | 🟩 +1.96% | 🟥 -0.45% | 🟩 +1.29% | 🟥 -1.54% | 🟩 +1.85% | 🟥 -3.21% | 🟥 -0.62% | 🟩 +2.01% | 🟩 +0.89% | 🟩 +0.91% |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 2025 | 🟩 +0.75% | 🟥 -0.71% | 🟩 +0.53% | 🟥 -0.11% | 🟩 +0.76% | 🟥 -0.12% | 🟩 +1.69% | 🟩 +0.09% | 🟩 +1.65% | 🟩 +3.47% | 🟩 +0.72% | 🟥 -1.27% |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | 2026 | 🟥 -2.14% | 🟩 +2.45% | 🟩 +0.10% | 🟩 +0.95% | 🟩 +4.51% | 🟥 -0.16% | 🟩 +2.04% | 🟩 +3.00% | 🟩 +1.18% | — | — | — |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 2024 | 🟩 +11.32% | 🟩 +3.24% | 🟩 +0.89% | 🟥 -1.17% | 🟩 +1.38% | 🟩 +1.13% | 🟩 +0.78% | 🟩 +0.39% | 🟩 +0.80% | 🟥 -0.80% | 🟩 +2.86% | 🟥 -2.25% |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 2025 | 🟥 -3.38% | 🟩 +0.42% | 🟥 -3.98% | 🟥 -1.73% | 🟩 +1.27% | 🟩 +0.07% | 🟩 +0.33% | 🟥 -0.71% | 🟩 +0.06% | 🟥 -1.74% | 🟩 +7.37% | 🟩 +1.94% |
| SFIN · 1H · `bollinger-confirmed-breakout_30` | 2026 | 🟩 +6.54% | 🟥 -1.35% | 🟩 +1.38% | 🟥 -1.21% | 🟩 +7.80% | 🟩 +2.02% | 🟩 +17.04% | 🟩 +4.61% | 🟥 -2.05% | — | — | — |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 2024 | 🟥 -0.22% | 🟩 +0.17% | 🟩 +1.64% | 🟩 +0.97% | 🟩 +0.94% | 🟥 -1.91% | 🟩 +1.42% | 🟩 +1.02% | 🟥 -0.70% | 🟩 +0.23% | 🟩 +0.15% | 🟩 +2.94% |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 2025 | 🟥 -0.35% | 🟩 +1.47% | 🟩 +0.13% | 🟥 -0.85% | 🟩 +0.49% | 🟥 -1.77% | 🟩 +0.46% | 🟩 +4.43% | 🟥 -0.79% | 🟩 +2.15% | 🟩 +0.09% | 🟥 -0.64% |
| AFLT · 4H · `bollinger-confirmed-breakout_20` | 2026 | 🟥 -0.90% | 🟥 -1.41% | 🟩 +1.58% | 🟩 +0.42% | 🟥 -0.65% | 🟩 +0.90% | 🟩 +1.67% | 🟩 +1.01% | 🟥 -1.27% | — | — | — |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 2024 | — | ⬜ +0.00% | ⬜ +0.00% | ⬜ +0.00% | 🟩 +0.29% | 🟩 +0.64% | 🟩 +3.04% | 🟥 -0.54% | 🟩 +0.10% | 🟩 +0.93% | 🟩 +4.75% | 🟥 -2.10% |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 2025 | ⬜ +0.00% | 🟩 +0.94% | 🟩 +2.59% | 🟩 +0.90% | 🟩 +0.81% | 🟩 +0.12% | 🟩 +1.61% | 🟩 +0.01% | 🟩 +1.93% | 🟩 +0.88% | 🟥 -0.24% | 🟩 +2.41% |
| DIAS · 1D · `bollinger-confirmed-breakout_30` | 2026 | 🟥 -0.14% | 🟩 +0.19% | 🟥 -1.04% | 🟩 +2.43% | 🟩 +4.30% | 🟩 +0.70% | 🟩 +0.47% | 🟥 -1.75% | 🟥 -0.01% | — | — | — |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 2024 | 🟥 -1.24% | 🟥 -1.68% | 🟥 -0.30% | 🟥 -0.93% | 🟩 +1.31% | 🟥 -2.17% | 🟩 +1.27% | 🟩 +1.36% | 🟩 +0.95% | 🟩 +0.88% | 🟩 +1.84% | 🟩 +1.18% |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 2025 | 🟩 +1.10% | 🟩 +0.83% | 🟩 +0.77% | 🟩 +0.19% | 🟩 +2.03% | 🟥 -0.88% | 🟩 +2.87% | 🟩 +0.58% | 🟩 +0.58% | 🟥 -2.21% | 🟥 -2.47% | 🟥 -0.62% |
| ROLO · 1H · `bollinger-confirmed-breakout_30` | 2026 | 🟩 +3.54% | 🟥 -1.69% | 🟥 -1.21% | 🟩 +1.52% | 🟩 +0.47% | 🟩 +2.78% | 🟩 +5.83% | 🟥 -1.79% | 🟩 +1.62% | — | — | — |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2024 | 🟩 +0.64% | 🟩 +1.42% | 🟥 -1.09% | 🟥 -2.97% | 🟩 +3.45% | 🟥 -0.51% | 🟩 +1.42% | 🟥 -0.83% | 🟩 +5.47% | 🟩 +3.66% | 🟩 +0.40% | 🟩 +2.91% |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2025 | 🟥 -1.28% | 🟩 +0.78% | 🟥 -2.00% | 🟥 -0.89% | 🟥 -0.20% | 🟥 -0.03% | 🟥 -1.22% | 🟩 +1.35% | 🟩 +0.10% | 🟥 -2.38% | 🟩 +0.13% | 🟩 +0.08% |
| EUTR · 4H · `bollinger-confirmed-breakout_20` | 2026 | 🟩 +0.55% | 🟥 -0.97% | 🟩 +0.66% | 🟩 +4.95% | 🟩 +0.45% | 🟩 +0.63% | 🟩 +2.71% | 🟩 +2.29% | 🟩 +0.25% | — | — | — |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 2024 | ⬜ +0.00% | 🟥 -0.95% | 🟥 -0.66% | 🟥 -1.31% | 🟩 +3.17% | 🟥 -0.51% | 🟩 +1.15% | 🟩 +2.82% | 🟩 +2.32% | 🟩 +0.75% | 🟩 +2.75% | 🟩 +1.07% |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 2025 | 🟩 +2.17% | 🟥 -3.03% | 🟩 +1.82% | 🟩 +1.44% | 🟩 +0.50% | 🟥 -0.83% | 🟩 +1.07% | 🟥 -0.08% | 🟩 +1.47% | 🟩 +0.50% | 🟥 -0.24% | 🟥 -0.35% |
| ROLO · 4H · `bollinger-confirmed-breakout_20` | 2026 | 🟩 +3.28% | 🟥 -0.78% | 🟩 +0.25% | 🟩 +2.49% | 🟩 +2.19% | 🟩 +3.05% | 🟥 -0.69% | 🟩 +1.61% | 🟩 +0.11% | — | — | — |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 2024 | ⬜ +0.00% | 🟥 -1.35% | 🟥 -0.24% | 🟩 +2.55% | 🟩 +6.04% | 🟩 +0.57% | 🟥 -1.60% | 🟩 +1.86% | 🟩 +0.97% | 🟥 -4.35% | 🟩 +1.68% | 🟩 +1.36% |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 2025 | 🟥 -0.33% | 🟩 +1.39% | 🟩 +0.26% | 🟩 +2.94% | 🟩 +2.42% | 🟥 -0.92% | 🟩 +1.45% | 🟩 +0.51% | 🟩 +1.03% | 🟥 -1.03% | 🟥 -0.68% | 🟩 +0.22% |
| UNAC · 4H · `bollinger-confirmed-breakout_30` | 2026 | 🟥 -1.09% | 🟩 +0.91% | 🟥 -0.23% | 🟥 -1.62% | 🟩 +2.03% | 🟩 +3.71% | 🟩 +4.63% | 🟩 +3.21% | 🟩 +1.10% | — | — | — |

## Как читать результат

Все пары, включая убыточные и правила с несколькими удачными месяцами, есть в [таблице пар](monthly_case_summary.csv). Исходные [месяцы](monthly_returns.csv) и [разбивка по фазам](monthly_regime_profiles.csv) сохранены отдельно. Если фазы рынка размечены после завершения месяца, их нельзя использовать как сигнал того же месяца.

Неполный последний месяц не включён в годовой итог. Доходность одной пары не равна доходности общего портфеля. Если модель расходов `gross_before_costs`, результат до комиссии, спреда, проскальзывания, дивидендов и стоимости short. История уже просмотрена при выборе гипотезы; статус `REVIEW_ONLY`.

## Long и short по отдельности

Доля удачных сделок считается **только по закрытым сделкам**. Доходность включает переоценку открытой позиции и потому не выводится из этой доли. Сравнение направлений проведено на уже просмотренной истории; это гипотеза для отдельной проверки.

| Акция · интервал · вариант | Режим | Закрыто long / выигрыш | Закрыто short / выигрыш | Плюсовые месяцы | Вывод |
|---|---|---:|---:|---:|---|
| MSNG · 4H · `bollinger-confirmed-breakout_30` | long_only | 10/30 · 33.3% | 0 · — | 12/33 | diagnostic_only; selected examples, not whole grid |
| MSNG · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 20/37 · 54.1% | 18/33 | diagnostic_only; selected examples, not whole grid |
| MTLR · 4H · `bollinger-confirmed-breakout_30` | long_only | 9/27 · 33.3% | 0 · — | 8/33 | diagnostic_only; selected examples, not whole grid |
| MTLR · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 20/41 · 48.8% | 16/33 | diagnostic_only; selected examples, not whole grid |
| UGLD · 4H · `bollinger-confirmed-breakout_30` | long_only | 14/30 · 46.7% | 0 · — | 15/33 | diagnostic_only; selected examples, not whole grid |
| UGLD · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 16/26 · 61.5% | 14/33 | diagnostic_only; selected examples, not whole grid |
| RTKM · 4H · `bollinger-confirmed-breakout_30` | long_only | 11/35 · 31.4% | 0 · — | 9/33 | diagnostic_only; selected examples, not whole grid |
| RTKM · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 22/39 · 56.4% | 18/33 | diagnostic_only; selected examples, not whole grid |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | long_only | 9/27 · 33.3% | 0 · — | 9/33 | diagnostic_only; selected examples, not whole grid |
| WUSH · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 22/36 · 61.1% | 18/33 | diagnostic_only; selected examples, not whole grid |
| VSEH · 4H · `bollinger-confirmed-breakout_30` | long_only | 8/25 · 32.0% | 0 · — | 9/33 | diagnostic_only; selected examples, not whole grid |
| VSEH · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 12/25 · 48.0% | 14/33 | diagnostic_only; selected examples, not whole grid |
| SPBE · 4H · `bollinger-confirmed-breakout_30` | long_only | 12/31 · 38.7% | 0 · — | 13/33 | diagnostic_only; selected examples, not whole grid |
| SPBE · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 15/35 · 42.9% | 11/33 | diagnostic_only; selected examples, not whole grid |
| AFKS · 4H · `bollinger-confirmed-breakout_30` | long_only | 16/31 · 51.6% | 0 · — | 13/33 | diagnostic_only; selected examples, not whole grid |
| AFKS · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 20/32 · 62.5% | 14/33 | diagnostic_only; selected examples, not whole grid |
| AFLT · 4H · `bollinger-confirmed-breakout_30` | long_only | 14/31 · 45.2% | 0 · — | 15/33 | diagnostic_only; selected examples, not whole grid |
| AFLT · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 17/40 · 42.5% | 17/33 | diagnostic_only; selected examples, not whole grid |
| MGNT · 4H · `bollinger-confirmed-breakout_30` | long_only | 11/29 · 37.9% | 0 · — | 10/33 | diagnostic_only; selected examples, not whole grid |
| MGNT · 4H · `bollinger-confirmed-breakout_30` | short_only | 0 · — | 23/42 · 54.8% | 15/33 | diagnostic_only; selected examples, not whole grid |

[Все результаты по направлениям](trade_side_summary.csv). Если капитал уходит ниже нуля, вариант недопустим независимо от процента успешных сделок.

## Источник торговой идеи

Автор: John Bollinger. [Первоисточник](https://www.bollingerbands.com/_files/ugd/58be43_d09c50b6e8ea4afd9af0523ef94de876.pdf). Тип свидетельства: `mechanical_interpretation`.

Механическое правило этого теста: Two consecutive closes outside the same Bollinger Band; exit at middle band. The published Method IV also uses ADX, omitted here as a deliberate isolated test.

Полный личный журнал сделок не подтверждён; результаты выше относятся только к проверке сформулированной версии на локальных свечах.
