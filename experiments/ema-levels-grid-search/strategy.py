"""EMA 45 bounce zone, selected from the standalone EMA levels experiment."""

from __future__ import annotations

import math

STRATEGY_ID = "ema-level-45-atr025-long-short-1h"
SYMBOL = "SMLT"
TIMEFRAME = "1H"
EMA_PERIOD = 45
ATR_DISTANCE = 0.25


def signal(bars: list[dict]) -> int:
    if not bars:
        return 0
    level = bars[0]["close"]
    alpha = 2 / (EMA_PERIOD + 1)
    ranges: list[float] = []
    previous_up = previous_down = False
    event = 0
    for index, bar in enumerate(bars):
        if index:
            level += alpha * (bar["close"] - level)
        previous_close = bars[index - 1]["close"] if index else bar["close"]
        tr = max(bar["high"] - bar["low"],
                 abs(bar["high"] - previous_close), abs(bar["low"] - previous_close))
        ranges.append(tr)
        if len(ranges) > 14:
            ranges.pop(0)
        valid = index >= max(EMA_PERIOD, 14) and len(ranges) == 14
        width = ATR_DISTANCE * sum(ranges) / 14 if valid else math.nan
        up = valid and level - width <= bar["low"] <= level + width and bar["close"] > level
        down = valid and level - width <= bar["high"] <= level + width and bar["close"] < level
        event = 1 if up and not previous_up and not down else -1 if down and not previous_down and not up else 0
        previous_up, previous_down = up, down
    return event


def target_side(bars: list[dict]) -> str | None:
    event = signal(bars)
    return "long" if event > 0 else "short" if event < 0 else None
