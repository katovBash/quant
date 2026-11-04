"""Causal weekly trendline and coarse volume-at-price proxies for research."""

from __future__ import annotations

import math
from bisect import bisect_left
from datetime import date

from src.ema.core.scan_ema import aggregate
from src.research.standalone_grid import atr


def week_key(stamp: str) -> tuple[int, int]:
    return date.fromisoformat(stamp[:10]).isocalendar()[:2]


def project(points: list[tuple[int, float]], target: int) -> float:
    (x1, y1), (x2, y2) = points
    return y2 + (y2 - y1) * (target - x2) / (x2 - x1)


def _best_line(points: list[tuple[int, float]], weekly: list[dict],
               weekly_atr: list[float], as_of: int, side: str,
               min_touches: int) -> float:
    """Prefer more independent pivot touches, then a longer base; reject broken lines."""
    best_key = None
    best_value = math.nan
    for left in range(max(0, len(points) - 8), len(points) - 1):
        for right in range(left + 1, len(points)):
            first, second = points[left], points[right]
            base = second[0] - first[0]
            if base < 2 or as_of + 1 - second[0] > 2 * base:
                continue
            value = project([first, second], as_of + 1)
            if not math.isfinite(value) or value <= 0:
                continue
            touched = sum(
                abs(price - project([first, second], x)) <= 0.5 * weekly_atr[x]
                for x, price in points if first[0] <= x <= as_of
                and math.isfinite(weekly_atr[x]))
            if touched < min_touches:
                continue
            broken = any(
                (weekly[x]["close"] < project([first, second], x) - 0.5 * weekly_atr[x]
                 if side == "support" else
                 weekly[x]["close"] > project([first, second], x) + 0.5 * weekly_atr[x])
                for x in range(second[0] + 1, as_of + 1)
                if math.isfinite(weekly_atr[x]))
            if broken:
                continue
            key = (touched, base, second[0])
            if best_key is None or key > best_key:
                best_key, best_value = key, value
    return best_value


def weekly_trendlines(daily: list[dict], wing: int, swing_atr: float,
                      min_touches: int) -> tuple[list[dict], list[tuple[float, float]]]:
    """Documented Auto Trendlines-like weekly pivots, not TradingView's exact code."""
    weekly = aggregate(daily, "1W")
    vol = atr(weekly, 14)
    swings: list[tuple[str, int, float]] = []
    levels = []
    for as_of in range(len(weekly)):
        pivot = as_of - wing
        if pivot >= wing and math.isfinite(vol[pivot]):
            near = weekly[pivot - wing:pivot + wing + 1]
            high = weekly[pivot]["high"]
            low = weekly[pivot]["low"]
            candidates = []
            if high > max(x["high"] for x in near[:wing]) and high >= max(x["high"] for x in near[wing + 1:]):
                candidates.append(("high", high))
            if low < min(x["low"] for x in near[:wing]) and low <= min(x["low"] for x in near[wing + 1:]):
                candidates.append(("low", low))
            for kind, price in candidates:
                if not swings:
                    swings.append((kind, pivot, price))
                elif swings[-1][0] == kind:
                    more_extreme = price > swings[-1][2] if kind == "high" else price < swings[-1][2]
                    if more_extreme:
                        swings[-1] = kind, pivot, price
                elif abs(price - swings[-1][2]) >= swing_atr * vol[pivot]:
                    swings.append((kind, pivot, price))
        highs = [(x, price) for kind, x, price in swings if kind == "high"]
        lows = [(x, price) for kind, x, price in swings if kind == "low"]
        resistance = _best_line(highs, weekly, vol, as_of, "resistance", min_touches)
        support = _best_line(lows, weekly, vol, as_of, "support", min_touches)
        levels.append((resistance, support))
    return weekly, levels


def _profile(daily: list[dict], bins: int = 48) -> tuple[float, float, float]:
    """Uniformly allocate each daily candle's volume across its high-low bins."""
    lo, hi = min(x["low"] for x in daily), max(x["high"] for x in daily)
    if hi <= lo or not any(x.get("volume", 0) > 0 for x in daily):
        return math.nan, math.nan, math.nan
    width = (hi - lo) / bins
    mass = [0.0] * bins
    for bar in daily:
        volume = max(float(bar.get("volume", 0)), 0)
        first = max(0, min(bins - 1, int((bar["low"] - lo) / width)))
        last = max(0, min(bins - 1, int((bar["high"] - lo) / width)))
        each = volume / (last - first + 1)
        for index in range(first, last + 1):
            mass[index] += each
    poc = max(range(bins), key=lambda index: mass[index])
    left = right = poc
    included = mass[poc]
    target = 0.7 * sum(mass)
    while included < target and (left > 0 or right < bins - 1):
        below = mass[left - 1] if left > 0 else -1
        above = mass[right + 1] if right < bins - 1 else -1
        if above >= below:
            right += 1
            included += mass[right]
        else:
            left -= 1
            included += mass[left]
    return lo + (left + 0.5) * width, lo + (right + 0.5) * width, lo + (poc + 0.5) * width


def weekly_volume_profile(daily: list[dict], window_weeks: int) -> tuple[list[dict], list[tuple[float, float]]]:
    weekly = aggregate(daily, "1W")
    keys = [week_key(x["ts"]) for x in daily]
    levels = []
    for as_of in range(len(weekly)):
        if as_of + 1 < window_weeks:
            levels.append((math.nan, math.nan))
            continue
        first_week = week_key(weekly[as_of + 1 - window_weeks]["ts"])
        last_week = week_key(weekly[as_of]["ts"])
        bars = [bar for bar, key in zip(daily, keys) if first_week <= key <= last_week]
        low, high, _ = _profile(bars)
        levels.append((high, low))
    return weekly, levels


def map_prior_week(signal_bars: list[dict], weekly: list[dict],
                   levels: list[tuple[float, float]]) -> list[tuple[float, float]]:
    keys = [week_key(x["ts"]) for x in weekly]
    return [levels[index] if (index := bisect_left(keys, week_key(bar["ts"])) - 1) >= 0
            else (math.nan, math.nan) for bar in signal_bars]


def confluence(trend: list[tuple[float, float]], profile: list[tuple[float, float]],
               volatility: list[float], tolerance_atr: float = 2) -> list[tuple[float, float]]:
    result = []
    for (tr, ts), (pr, ps), v in zip(trend, profile, volatility):
        resistance = tr if math.isfinite(tr) and math.isfinite(pr) and abs(tr - pr) <= tolerance_atr * v else math.nan
        support = ts if math.isfinite(ts) and math.isfinite(ps) and abs(ts - ps) <= tolerance_atr * v else math.nan
        result.append((resistance, support))
    return result


def rejection_signals(bars: list[dict], levels: list[tuple[float, float]],
                      volatility: list[float], band_atr: float = 0.5) -> list[int]:
    out = [0] * len(bars)
    prior_up = prior_down = False
    for i in range(33, len(bars)):
        resistance, support = levels[i]
        v = volatility[i]
        if not math.isfinite(v) or v <= 0:
            continue
        width = band_atr * v
        bar = bars[i]
        up = (math.isfinite(support) and support - width <= bar["low"] <= support + width
              and bar["close"] > support)
        down = (math.isfinite(resistance) and resistance - width <= bar["high"] <= resistance + width
                and bar["close"] < resistance)
        if up and not prior_up and not down:
            out[i] = 1
        elif down and not prior_down and not up:
            out[i] = -1
        prior_up, prior_down = up, down
    return out
