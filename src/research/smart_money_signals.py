"""Causal OHLC interpretation of a liquidity sweep followed by an FVG."""

from __future__ import annotations

from collections import deque


def _atr14(bars: list[dict]) -> list[float | None]:
    result = [None] * len(bars)
    window: deque[float] = deque()
    total = 0.0
    for index, bar in enumerate(bars):
        previous = bars[index - 1]["close"] if index else bar["close"]
        value = max(bar["high"] - bar["low"], abs(bar["high"] - previous),
                    abs(bar["low"] - previous))
        window.append(value)
        total += value
        if len(window) > 14:
            total -= window.popleft()
        if len(window) == 14:
            result[index] = total / 14
    return result


def _prior_extrema(bars: list[dict], length: int) -> tuple[list[float | None], list[float | None]]:
    highs: deque[int] = deque()
    lows: deque[int] = deque()
    prior_high = [None] * len(bars)
    prior_low = [None] * len(bars)
    for index, bar in enumerate(bars):
        while highs and highs[0] < index - length:
            highs.popleft()
        while lows and lows[0] < index - length:
            lows.popleft()
        if index >= length:
            prior_high[index] = bars[highs[0]]["high"]
            prior_low[index] = bars[lows[0]]["low"]
        while highs and bars[highs[-1]]["high"] <= bar["high"]:
            highs.pop()
        highs.append(index)
        while lows and bars[lows[-1]]["low"] >= bar["low"]:
            lows.pop()
        lows.append(index)
    return prior_high, prior_low


def _direction(up: bool, down: bool) -> int:
    return 1 if up and not down else -1 if down and not up else 0


def all_variants(bars: list[dict]) -> dict[str, tuple[list[int], list[int]]]:
    n = len(bars)
    atr = _atr14(bars)
    prior = {length: _prior_extrema(bars, length) for length in (10, 20)}
    exit_high, exit_low = prior[10]
    exits = [0] * n
    for i, bar in enumerate(bars):
        if exit_low[i] is not None:
            exits[i] = _direction(bar["close"] > exit_high[i], bar["close"] < exit_low[i])
    sweeps = {}
    for length in (10, 20):
        highs, lows = prior[length]
        for depth in (0, 0.25):
            values = [0] * n
            for i, bar in enumerate(bars):
                if atr[i] is None or lows[i] is None:
                    continue
                up = bar["low"] < lows[i] - depth * atr[i] and bar["close"] > lows[i]
                down = bar["high"] > highs[i] + depth * atr[i] and bar["close"] < highs[i]
                values[i] = _direction(up, down)
            sweeps[(length, depth)] = values
    gaps = {}
    for minimum in (0, 0.2):
        values = [0] * n
        for i in range(2, n):
            if atr[i] is None:
                continue
            up = bars[i]["low"] > bars[i - 2]["high"] + minimum * atr[i]
            down = bars[i]["high"] < bars[i - 2]["low"] - minimum * atr[i]
            values[i] = _direction(up, down)
        gaps[minimum] = values
    result = {}
    for (length, depth), values in sweeps.items():
        result[f"sweep_{length}_{depth:g}"] = (values, exits)
    for minimum, values in gaps.items():
        result[f"fvg_{minimum:g}"] = (values, exits)
    for (length, depth), sweep in sweeps.items():
        for minimum, fvg in gaps.items():
            for window in (1, 3):
                values = [0] * n
                last_up = last_down = -1_000_000
                for i in range(n):
                    if fvg[i] == 1 and 0 < i - last_up <= window:
                        values[i] = 1
                    elif fvg[i] == -1 and 0 < i - last_down <= window:
                        values[i] = -1
                    if sweep[i] == 1:
                        last_up = i
                    elif sweep[i] == -1:
                        last_down = i
                result[f"smc_{length}_{depth:g}_{minimum:g}_{window}"] = (values, exits)
    return result
