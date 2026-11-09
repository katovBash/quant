# Отбор акций для paper trading

Первый допуск: **строго >10%** после расходов за последние полные 12 месяцев по каждой акции. Все непрерывные трёхмесячные и годовые окна сохранены в [машинном отчёте](paper_selection.json) для оценки устойчивости; для них нет дополнительного порога допуска.

Хотя бы одна акция прошла порог у 5 из 6 стратегий. Допуск оценивается по каждой акции; фиксированного размера корзины нет.

| Стратегия | Акция | 12 месяцев | 3 месяца | Положительных 3-месячных окон | Худшее 3-месячное окно | Допуск |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `dennis-turtle-30-20-1d` | VSEH | +3.84% | -0.67% | 20/25 | -1.00% | FAIL_12M |
| `dennis-turtle-30-20-1d` | WUSH | +2.74% | -0.60% | 21/31 | -5.69% | FAIL_12M |
| `dennis-turtle-30-20-1d` | POSI | +5.89% | +1.94% | 26/31 | -2.58% | FAIL_12M |
| `dennis-turtle-30-20-1d` | LENT | -3.72% | -7.12% | 20/31 | -7.92% | FAIL_12M |
| `dennis-turtle-30-20-1d` | VKCO | +14.89% | +4.97% | 26/31 | -0.87% | PASS_12M |
| `dennis-turtle-30-20-1d` | NLMK | +0.64% | -2.30% | 25/31 | -5.87% | FAIL_12M |
| `dennis-turtle-30-20-1d` | BELU | +2.52% | -2.57% | 20/31 | -3.47% | FAIL_12M |
| `dennis-turtle-30-20-1d` | ENPG | +0.49% | -2.32% | 21/31 | -4.05% | FAIL_12M |
| `dennis-turtle-30-20-1d` | MSNG | +1.29% | -4.79% | 22/31 | -8.56% | FAIL_12M |
| `dennis-turtle-30-20-1d` | GMKN | +0.45% | +0.25% | 18/31 | -6.38% | FAIL_12M |
| `dennis-turtle-55-20-1h` | SFIN | +56.62% | +14.01% | 26/31 | -1.08% | PASS_12M |
| `dennis-turtle-55-20-1h` | WUSH | +31.65% | +17.83% | 25/31 | -3.89% | PASS_12M |
| `dennis-turtle-55-20-1h` | MTLR | +1.97% | +1.90% | 23/31 | -1.95% | FAIL_12M |
| `dennis-turtle-55-20-1h` | EUTR | +10.22% | +5.62% | 18/31 | -4.91% | PASS_12M |
| `dennis-turtle-55-20-1h` | NLMK | -5.31% | -2.03% | 20/31 | -4.92% | FAIL_12M |
| `dennis-turtle-55-20-1h` | LKOH | +1.73% | +2.61% | 14/31 | -4.06% | FAIL_12M |
| `dennis-turtle-55-20-1h` | SVCB | +0.56% | +1.86% | 16/31 | -4.85% | FAIL_12M |
| `dennis-turtle-55-20-1h` | IRKT | +12.62% | +10.49% | 24/31 | -4.42% | PASS_12M |
| `dennis-turtle-55-20-1h` | MRKC | +15.35% | +5.11% | 26/31 | -2.61% | PASS_12M |
| `dennis-turtle-55-20-1h` | ROSN | +6.07% | +3.76% | 19/31 | -5.17% | FAIL_12M |
| `line-retest-4h-wing1-zone05-slope` | IRKT | +9.64% | +10.57% | 26/31 | -3.54% | FAIL_12M |
| `line-retest-4h-wing1-zone05-slope` | WUSH | +33.62% | +12.99% | 26/31 | -3.39% | PASS_12M |
| `line-retest-4h-wing1-zone1-slope` | IRKT | +10.99% | +7.44% | 24/31 | -3.12% | PASS_12M |
| `line-retest-4h-wing2-zone1-slope` | MGNT | -1.18% | -2.69% | 21/31 | -3.97% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | MTSS | +2.35% | +2.41% | 20/31 | -7.26% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | VSEH | +1.61% | -0.40% | 19/25 | -2.90% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | WUSH | +2.79% | +4.70% | 21/31 | -9.59% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | VKCO | +6.51% | -0.25% | 25/31 | -3.97% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | RTKM | +2.82% | -0.88% | 21/31 | -7.30% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | SNGSP | -0.31% | +3.10% | 18/31 | -4.42% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | NVTK | -1.20% | +0.55% | 18/31 | -6.73% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | POSI | +11.40% | +3.80% | 25/31 | -4.10% | PASS_12M |
| `zigzag-confirmed-breakout-5-6-1d` | MAGN | +5.35% | -1.77% | 22/31 | -1.77% | FAIL_12M |
| `zigzag-confirmed-breakout-5-6-1d` | LENT | -3.89% | -2.24% | 19/31 | -6.22% | FAIL_12M |
