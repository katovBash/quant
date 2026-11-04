"""Causal horizontal daily/weekly levels and close-confirmed breakout events."""

from __future__ import annotations

import math
from bisect import bisect_left
from datetime import date

from src.ema.core.scan_ema import aggregate
from src.research.standalone_grid import atr


def _key(stamp: str, source: str):
    day = date.fromisoformat(stamp[:10])
    return day.isoformat() if source == "1D" else day.isocalendar()[:2]


def levels(bars: list[dict], daily: list[dict], source: str,
           lookback: int) -> list[tuple[float, float]]:
    """Prior completed higher bars; current day/week is unavailable at signal time."""
    if source not in ("1D", "1W") or lookback < 2:
        raise ValueError("invalid source or lookback")
    higher = daily if source == "1D" else aggregate(daily, "1W")
    keys = [_key(bar["ts"], source) for bar in higher]
    result = []
    for bar in bars:
        last = bisect_left(keys, _key(bar["ts"], source)) - 1
        if last + 1 < lookback:
            result.append((math.nan, math.nan))
            continue
        window = higher[last + 1 - lookback:last + 1]
        result.append((max(item["high"] for item in window),
                       min(item["low"] for item in window)))
    return result


def breakout_events(bars: list[dict], boundaries: list[tuple[float, float]],
                    buffer_atr: float, *, min_width_atr: float = 4.0) -> list[int]:
    """First signal-close outside a mature range; returns 1, -1 or zero."""
    if len(bars) != len(boundaries) or buffer_atr < 0 or min_width_atr < 0:
        raise ValueError("invalid breakout inputs")
    vol = atr(bars, 14)
    result = [0] * len(bars)
    for i in range(1, len(bars)):
        resistance, support = boundaries[i]
        if not (math.isfinite(resistance) and math.isfinite(support)
                and math.isfinite(vol[i]) and vol[i] > 0
                and resistance - support >= min_width_atr * vol[i]):
            continue
        upper = resistance + buffer_atr * vol[i]
        lower = support - buffer_atr * vol[i]
        if bars[i - 1]["close"] <= upper < bars[i]["close"]:
            result[i] = 1
        elif bars[i - 1]["close"] >= lower > bars[i]["close"]:
            result[i] = -1
    return result


def retest_events(bars: list[dict], boundaries: list[tuple[float, float]],
                  breakout: list[int], *, ttl: int = 8,
                  zone_atr: float = 0.25) -> list[int]:
    """One later rejection of the frozen broken level; invalidate a failed break."""
    if not (len(bars) == len(boundaries) == len(breakout)) or ttl < 1 or zone_atr <= 0:
        raise ValueError("invalid retest inputs")
    vol = atr(bars, 14)
    result = [0] * len(bars)
    armed_side, armed_index, level = 0, -1, math.nan
    for i, (bar, event) in enumerate(zip(bars, breakout)):
        if event:
            armed_side, armed_index = event, i
            level = boundaries[i][0] if event > 0 else boundaries[i][1]
            continue
        if not armed_side or i - armed_index > ttl:
            armed_side = 0
            continue
        if armed_side > 0 and bar["close"] <= level or armed_side < 0 and bar["close"] >= level:
            armed_side = 0
            continue
        width = zone_atr * vol[i]
        if not math.isfinite(width) or width <= 0:
            continue
        if armed_side > 0 and level-width <= bar["low"] <= level+width and bar["close"] > level:
            result[i] = 1
            armed_side = 0
        elif armed_side < 0 and level-width <= bar["high"] <= level+width and bar["close"] < level:
            result[i] = -1
            armed_side = 0
    return result


def local_control(bars: list[dict], lookback: int = 20) -> list[int]:
    """First 20-signal-bar close beyond preceding local high/low."""
    result = [0] * len(bars)
    for i in range(lookback, len(bars)):
        prior = bars[i-lookback:i]
        high = max(bar["high"] for bar in prior)
        low = min(bar["low"] for bar in prior)
        if bars[i-1]["close"] <= high < bars[i]["close"]:
            result[i] = 1
        elif bars[i-1]["close"] >= low > bars[i]["close"]:
            result[i] = -1
    return result
