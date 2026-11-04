# EMA12/33 long + short · ADX14

Отдельный эксперимент: вход long после пересечения EMA12 выше EMA33 и short после пересечения вниз, только когда ADX14 ≥20 (или 25 в переключателе Pine). Обратное пересечение всегда закрывает старую позицию; при слабом тренде остаёмся без позиции. Сделка исполняется на следующем баре.

[Pine для TradingView](../strategy.pine) · [сравнение по всему кэшу](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/adx-filter/execute/RESEARCH.md) · [все результаты CSV](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/adx-filter/execute/all_results.csv) · [тикеры](tickers/README.md) · [исторический отбор](success/README.md).

Капитал 1 млн ₽, 25% на вход, комиссия 0,05% за сторону, проскальзывание 1 тик. Локальный симулятор и TradingView могут различаться по свечам и исполнению. Заём для short и дивидендные обязательства не учтены.
