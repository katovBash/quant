"""Causal, confirmed-swing Fibonacci retracement signals."""

from __future__ import annotations

import math

from src.research.standalone_grid import atr


def confirmed_swings(bars: list[dict], wing: int) -> list[tuple[tuple[int, float] | None,
                                                               tuple[int, float] | None]]:
    """At bar i return pivots confirmed strictly before that bar closes."""
    last_low = last_high = None
    states = []
    for i in range(len(bars)):
        states.append((last_low, last_high))
        j = i - wing
        if j < wing:
            continue
        window = bars[j - wing:i + 1]
        center = bars[j]
        if center["low"] < min(bar["low"] for bar in window[:wing]) and center["low"] <= min(
                bar["low"] for bar in window[wing + 1:]):
            last_low = (j, center["low"])
        if center["high"] > max(bar["high"] for bar in window[:wing]) and center["high"] >= max(
                bar["high"] for bar in window[wing + 1:]):
            last_high = (j, center["high"])
    return states


def retracement_signals(bars: list[dict], wing: int, ratio: float,
                        tolerance_atr: float) -> tuple[list[int], list[int]]:
    """First rejection of a confirmed swing's retracement; next-open fills elsewhere."""
    if wing < 1 or not 0 < ratio < 1 or tolerance_atr < 0:
        raise ValueError("invalid Fibonacci settings")
    states = confirmed_swings(bars, wing)
    volatility = atr(bars, 14)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    used_long = used_short = None
    for i, bar in enumerate(bars):
        low, high = states[i]
        if not low or not high or not math.isfinite(volatility[i]) or volatility[i] <= 0:
            continue
        low_j, low_price = low
        high_j, high_price = high
        if high_price <= low_price or high_price - low_price < 2 * volatility[i]:
            continue
        width = tolerance_atr * volatility[i]
        if high_j > low_j:
            anchor = (low_j, high_j)
            level = high_price - ratio * (high_price - low_price)
            if bar["close"] < low_price:
                exits[i] = -1
            if anchor != used_long and level - width <= bar["low"] <= level + width and bar["close"] > level:
                entries[i] = 1
                used_long = anchor
        elif low_j > high_j:
            anchor = (high_j, low_j)
            level = low_price + ratio * (high_price - low_price)
            if bar["close"] > high_price:
                exits[i] = 1
            if anchor != used_short and level - width <= bar["high"] <= level + width and bar["close"] < level:
                entries[i] = -1
                used_short = anchor
    return entries, exits
