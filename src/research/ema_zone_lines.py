"""Causal confirmed-pivot lines from completed 4H, daily or weekly candles."""

from __future__ import annotations

import math
from bisect import bisect_left
from datetime import date

from src.ema.core.scan_ema import aggregate, ema, four_hour
from src.research.standalone_grid import atr


def period_key(stamp: str, source: str) -> tuple[int, int] | str:
    day = date.fromisoformat(stamp[:10])
    return day.isoformat() if source == "1D" else day.isocalendar()[:2]


def pivot_history(bars: list[dict], wing: int) -> list[tuple[list[tuple[int, float]], list[tuple[int, float]]]]:
    """At completed period i, record only pivots with a closed right wing."""
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    history = []
    for i in range(len(bars)):
        pivot = i - wing
        if pivot >= wing:
            around = bars[pivot-wing:pivot+wing+1]
            high, low = bars[pivot]["high"], bars[pivot]["low"]
            if high > max(item["high"] for item in around[:wing]) and high >= max(item["high"] for item in around[wing+1:]):
                highs.append((pivot, high))
            if low < min(item["low"] for item in around[:wing]) and low <= min(item["low"] for item in around[wing+1:]):
                lows.append((pivot, low))
        history.append((highs[-2:].copy(), lows[-2:].copy()))
    return history


def projected_line(points: list[tuple[int, float]], target: int,
                   as_of: int, max_age: int) -> float:
    if len(points) < 2 or as_of - points[-1][0] > max_age:
        return math.nan
    (x1, y1), (x2, y2) = points
    return y2 + (y2-y1) * (target-x2) / (x2-x1)


def higher_lines(intraday: list[dict], daily: list[dict], source: str,
                 hourly: list[dict] | None = None, wing: int | None = None,
                 max_age: int | None = None) -> list[tuple[float, float]]:
    """Project last two confirmed highs/lows from prior completed source bars."""
    if source not in ("4H", "1D", "1W"):
        raise ValueError(source)
    if source == "4H":
        if hourly is None:
            raise ValueError("4H lines require hourly candles")
        higher = four_hour(hourly)
        default_wing, default_age = 1, 60
        starts = [bar["ts"] for bar in higher]
        hourly_stamps = [bar["ts"] for bar in hourly]
        keys = [hourly_stamps[bisect_left(hourly_stamps, starts[i + 1]) - 1]
                if i + 1 < len(starts) else hourly_stamps[-1]
                for i in range(len(starts))]
    else:
        higher = daily if source == "1D" else aggregate(daily, "1W")
        default_wing, default_age = (2, 60) if source == "1D" else (1, 26)
        keys = [period_key(bar["ts"], source) for bar in higher]
    wing = default_wing if wing is None else wing
    max_age = default_age if max_age is None else max_age
    if wing < 1 or max_age < 1:
        raise ValueError("wing and max_age must be positive")
    history = pivot_history(higher, wing)
    result = []
    for bar in intraday:
        key = bar["ts"] if source == "4H" else period_key(bar["ts"], source)
        last_complete = bisect_left(keys, key) - 1
        if last_complete < 0:
            result.append((math.nan, math.nan))
            continue
        highs, lows = history[last_complete]
        target = last_complete + 1
        resistance = projected_line(highs, target, last_complete, max_age)
        support = projected_line(lows, target, last_complete, max_age)
        result.append((resistance, support))
    return result


def higher_range_zones(intraday: list[dict], daily: list[dict], source: str,
                       window: int, min_touches: int = 1,
                       touch_range_fraction: float = 0.5) -> list[tuple[float, float]]:
    """Outer range boundaries of completed 1D/1W bars; never use the live period."""
    if source not in ("1D", "1W") or window < 3 or min_touches < 1:
        raise ValueError("invalid higher range configuration")
    higher = daily if source == "1D" else aggregate(daily, "1W")
    keys = [period_key(bar["ts"], source) for bar in higher]
    result = []
    for bar in intraday:
        last_complete = bisect_left(keys, period_key(bar["ts"], source)) - 1
        if last_complete + 1 < window:
            result.append((math.nan, math.nan))
            continue
        past = higher[last_complete + 1 - window:last_complete + 1]
        resistance = max(item["high"] for item in past)
        support = min(item["low"] for item in past)
        typical_range = sorted(item["high"] - item["low"] for item in past)[window // 2]
        tolerance = typical_range * touch_range_fraction
        high_touches = sum(item["high"] >= resistance - tolerance for item in past)
        low_touches = sum(item["low"] <= support + tolerance for item in past)
        result.append((resistance, support) if high_touches >= min_touches
                      and low_touches >= min_touches else (math.nan, math.nan))
    return result


def line_ema_gates(bars: list[dict], lines: list[tuple[float, float]],
                   distance_atr: float, bend_bars: int) -> tuple[list[bool], list[bool]]:
    """EMA25 bends down at projected resistance or up at projected support."""
    if bend_bars not in (1, 3) or distance_atr <= 0:
        raise ValueError("unsupported bend or zone width")
    levels = ema([bar["close"] for bar in bars], 25)
    volatility = atr(bars, 14)
    up_gate, down_gate = [False] * len(bars), [False] * len(bars)
    for i in range(max(33, bend_bars+1), len(bars)):
        resistance, support = lines[i]
        v = volatility[i]
        if not all(math.isfinite(value) for value in (resistance, support, v)) or v <= 0:
            continue
        if resistance <= support or resistance-support < 2*v:
            continue
        prior_slope = levels[i-1] - levels[i-bend_bars-1]
        current_slope = levels[i] - levels[i-bend_bars]
        bar = bars[i]
        width = distance_atr*v
        near_support = support-width <= bar["low"] <= support+width and bar["close"] > support
        near_resistance = resistance-width <= bar["high"] <= resistance+width and bar["close"] < resistance
        up_gate[i] = near_support and prior_slope <= 0 < current_slope and not near_resistance
        down_gate[i] = near_resistance and prior_slope >= 0 > current_slope and not near_support
    return up_gate, down_gate


def line_retest_signals(bars: list[dict], lines: list[tuple[float, float]],
                        distance_atr: float, ema_mode: str = "none",
                        bend_bars: int = 1,
                        min_channel_atr: float = 0) -> list[int]:
    """First rejection after two confirmed pivots define a line; next-open fill elsewhere."""
    if (distance_atr <= 0 or ema_mode not in ("none", "slope", "turn")
            or bend_bars < 1 or min_channel_atr < 0):
        raise ValueError("invalid retest parameters")
    levels = ema([bar["close"] for bar in bars], 25)
    volatility = atr(bars, 14)
    signals = [0] * len(bars)
    prior_support_contact = prior_resistance_contact = False
    for i in range(max(33, bend_bars + 1), len(bars)):
        resistance, support = lines[i]
        width = distance_atr * volatility[i]
        if min_channel_atr and (not math.isfinite(resistance) or not math.isfinite(support)
                                or not math.isfinite(volatility[i]) or
                                resistance - support < min_channel_atr * volatility[i]):
            prior_support_contact = prior_resistance_contact = False
            continue
        bar = bars[i]
        at_support = (math.isfinite(support) and math.isfinite(width) and width > 0
                      and support - width <= bar["low"] <= support + width
                      and bar["close"] > support)
        at_resistance = (math.isfinite(resistance) and math.isfinite(width) and width > 0
                         and resistance - width <= bar["high"] <= resistance + width
                         and bar["close"] < resistance)
        slope = levels[i] - levels[i - bend_bars]
        prior_slope = levels[i - 1] - levels[i - bend_bars - 1]
        allow_long = (ema_mode == "none" or slope > 0 and
                      (ema_mode == "slope" or prior_slope <= 0))
        allow_short = (ema_mode == "none" or slope < 0 and
                       (ema_mode == "slope" or prior_slope >= 0))
        if at_support and not prior_support_contact and not at_resistance and allow_long:
            signals[i] = 1
        elif at_resistance and not prior_resistance_contact and not at_support and allow_short:
            signals[i] = -1
        prior_support_contact = at_support
        prior_resistance_contact = at_resistance
    return signals
