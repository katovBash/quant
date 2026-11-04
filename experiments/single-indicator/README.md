# Один индикатор или один тип сигнала

Здесь индекс самостоятельных экспериментов: каждый проверяет одно семейство правил без фильтра из другого индикатора. Полные CSV и итоговые `SUMMARY.md` либо `REPORT.md` находятся внутри папки каждого эксперимента.

| Семейство | Эксперимент | Результат |
| --- | --- | --- |
| Скользящие средние | [EMA: пересечение](../ema-grid-search/README.md) | [Сводка](../ema-grid-search/SUMMARY.md) |
| Скользящие средние | [EMA: поддержка и сопротивление](../ema-levels-grid-search/README.md) | [Сводка](../ema-levels-grid-search/SUMMARY.md) |
| Скользящие средние | [SMA: пересечение](../sma-grid-search/README.md) | [Сводка](../sma-grid-search/SUMMARY.md) |
| Осциллятор | [RSI](../rsi-grid-search/README.md) | [Сводка](../rsi-grid-search/SUMMARY.md) |
| Сила и направление | [ADX и линии +DI/−DI](../adx-grid-search/README.md) | [Сводка](../adx-grid-search/SUMMARY.md) |
| Осциллятор | [CCI](../cci-grid-search/README.md) | [Сводка](../cci-grid-search/SUMMARY.md) |
| Осциллятор | [Williams %R](../williams-r-grid-search/README.md) | [Сводка](../williams-r-grid-search/SUMMARY.md) |
| Импульс | [ROC](../roc-grid-search/README.md) | [Сводка](../roc-grid-search/SUMMARY.md) |
| Импульс | [MACD](../macd-grid-search/README.md) | [Сводка](../macd-grid-search/SUMMARY.md) |
| Канал | [Bollinger](../bollinger-grid-search/README.md) | [Сводка](../bollinger-grid-search/SUMMARY.md) |
| Канал | [Donchian](../donchian-grid-search/README.md) | [Сводка](../donchian-grid-search/SUMMARY.md) |
| Ценовые уровни | [Четырёхточечные уровни](../four-point-levels-grid-search/README.md) | [Сводка](../four-point-levels-grid-search/SUMMARY.md) |
| Ценовые уровни | [Пробой границ 1D/1W](htf-level-breakouts/README.md) | [Помесячный отчёт](htf-level-breakouts/results/REPORT.md) |
| Свечи | [Паттерны](../patterns-grid-search/README.md) | [Сводка](../patterns-grid-search/SUMMARY.md) |

ADX с +DI/−DI и MACD со своей сигнальной линией остаются одним **семейством индикатора**. Пересечение двух EMA или SMA также считается одним семейством. `market-regime-grid-search` — отдельное исследование прогноза фаз рынка без торговли; оно перечислено в [общем индексе](../README.md).
