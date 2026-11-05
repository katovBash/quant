"""Causal, deliberately narrow Elliott impulse breakout proxies."""

from __future__ import annotations

from src.research.zigzag_signals import confirmed_pivots


def _setup(points: list[tuple[str, float, int, int]], pattern: str, side: str):
    count = 3 if pattern == "wave3" else 5
    if len(points) < count:
        return None
    recent = points[-count:]
    signs = [item[0] for item in recent]
    if side == "long":
        if signs != (["low", "high", "low"] if count == 3 else
                     ["low", "high", "low", "high", "low"]):
            return None
        prices = [item[1] for item in recent]
        if count == 3:
            l0, h1, l2 = prices
            valid = l0 < l2 < h1
            level = h1
        else:
            l0, h1, l2, h3, l4 = prices
            valid = l0 < l2 < h1 < l4 < h3
            level = h3
        return (level, recent[-1][3]) if valid else None
    if signs != (["high", "low", "high"] if count == 3 else
                 ["high", "low", "high", "low", "high"]):
        return None
    prices = [item[1] for item in recent]
    if count == 3:
        h0, l1, h2 = prices
        valid = l1 < h2 < h0
        level = l1
    else:
        h0, l1, h2, l3, h4 = prices
        valid = l3 < h4 < l1 < h2 < h0
        level = l3
    return (level, recent[-1][3]) if valid else None


def impulse_breakout_signals(bars: list[dict], pattern: str, wing: int,
                             deviation_pct: float) -> tuple[list[int], list[int]]:
    """Signal only after all setup pivots were confirmed on earlier bars."""
    if pattern not in ("wave3", "wave5"):
        raise ValueError(pattern)
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    points: list[tuple[str, float, int, int]] = []
    pending = iter(confirmed_pivots(bars, wing, deviation_pct))
    next_pivot = next(pending, None)
    used_long = used_short = -1
    for i in range(1, n):
        close = bars[i]["close"]
        previous = bars[i - 1]["close"]
        long = _setup(points, pattern, "long")
        short = _setup(points, pattern, "short")
        if long and previous <= long[0] < close and long[1] != used_long:
            entries[i] = 1
            used_long = long[1]
        elif short and previous >= short[0] > close and short[1] != used_short:
            entries[i] = -1
            used_short = short[1]
        latest_low = next((point[1] for point in reversed(points) if point[0] == "low"), None)
        latest_high = next((point[1] for point in reversed(points) if point[0] == "high"), None)
        if latest_low is not None and close < latest_low:
            exits[i] = -1
        elif latest_high is not None and close > latest_high:
            exits[i] = 1
        while next_pivot is not None and next_pivot[0] == i:
            confirmed, center, pivot_side, price = next_pivot
            point = (pivot_side, price, center, confirmed)
            if points and points[-1][0] == pivot_side:
                points[-1] = point
            else:
                points.append(point)
                if len(points) > 8:
                    del points[0]
            next_pivot = next(pending, None)
    return entries, exits
