# EMA12/33 + расширение диапазона свечи

Новый вход на пересечении EMA12/33 разрешён, если на текущей или одной из трёх предыдущих закрытых свечей **истинный диапазон превысил 1,5 среднего диапазона 20 свечей перед ней**. Это подтверждение движения, не стоп или отдельный сигнал. Встречное EMA-пересечение всегда закрывает старую позицию. [Pine](../strategy.pine).

[RTKM 1D](tickers/RTKM/README.md) — лучший подготовленный дневной пример с поздним win rate 70% при 10 сделках. [Весь перебор](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/pattern-lab/execute/all_results.csv), [методика](../../../legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/pattern-lab/execute/RESEARCH.md), [отбор](success/README.md), [тикеры](tickers/README.md). Результаты Pine и локального тестера ещё не сверены по сделкам; short не включает заём и дивидендные обязательства.
