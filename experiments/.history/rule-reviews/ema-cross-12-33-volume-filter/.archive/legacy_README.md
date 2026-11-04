# EMA12/33 + всплеск объёма

Новый вход на пересечении EMA12/33 разрешён, если на текущей или одной из трёх предыдущих закрытых свечей объём был **больше 1,5 среднего объёма 20 свечей перед ней**. Long/short направления задаёт пересечение EMA, встречный сигнал всегда закрывает старую позицию. Все параметры фиксированы до скана. [Pine](../strategy.pine).

Пример с достаточным числом сделок: [AFKS 4H](tickers/AFKS/README.md). Ещё один дневной пример: [ROSN 1D](tickers/ROSN/README.md). [Весь перебор](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/pattern-lab/execute/all_results.csv), [методика](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/pattern-lab/execute/RESEARCH.md), [отбор](success/README.md), [тикеры](tickers/README.md). Результаты локального симулятора ещё не сверены со сделками Pine в TradingView. Short без реальной платы за заём и дивидендных обязательств.
