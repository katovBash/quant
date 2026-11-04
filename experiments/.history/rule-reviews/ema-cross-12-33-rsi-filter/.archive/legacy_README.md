# EMA12/33 long + short · RSI14

Самостоятельный фильтр входа: при пересечении EMA12 выше EMA33 long разрешён только с RSI14 >50; при пересечении вниз short разрешён только с RSI14 <50. Обратный сигнал закрывает позицию даже если новый вход запрещён. Размер, комиссия и время исполнения идентичны базовой EMA12/33.

[Pine для TradingView](../strategy.pine) · [весь рынок](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/rsi-filter/execute/RESEARCH.md) · [CSV](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/rsi-filter/execute/all_results.csv) · [тикеры](tickers/README.md) · [исторический отбор](success/README.md).

RSI проверяется отдельно от ADX и трендовых линий. Локальные результаты требуют сверки сделок с TradingView; short не включает стоимость займа и дивидендные обязательства.
