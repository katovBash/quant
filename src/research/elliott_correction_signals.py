"""Causal price-geometry proxies for Elliott wave-2, wave-4 and A-B-C setups.

These are explicit OHLC rules, not a claim to identify discretionary wave counts.
"""

from __future__ import annotations

from src.research.zigzag_signals import confirmed_pivots


def _candidate(points: list[tuple[str, float, int]], pattern: str, direction: int,
               trigger_fraction: float):
    count = 5 if pattern == "wave4" else 4 if pattern == "abc" else 3
    if len(points) < count:
        return None
    recent = points[-count:]
    signs = [point[0] for point in recent]
    if pattern == "abc":
        expected = ["high", "low", "high", "low"] if direction == 1 else [
            "low", "high", "low", "high"]
    else:
        expected = (["low", "high", "low", "high", "low"] if count == 5 else
                    ["low", "high", "low"]) if direction == 1 else (
                    ["high", "low", "high", "low", "high"] if count == 5 else
                    ["high", "low", "high"])
    if signs != expected:
        return None
    p = [direction * point[1] for point in recent]
    if pattern == "wave2":
        low0, high1, low2 = p
        valid = low0 < low2 < high1
        ratio = (high1 - low2) / (high1 - low0) if high1 > low0 else 0
        threshold = low2 + trigger_fraction * (high1 - low2)
    elif pattern == "wave4":
        low0, high1, low2, high3, low4 = p
        valid = low0 < low2 < high1 < low4 < high3
        ratio = (high3 - low4) / (high3 - low2) if high3 > low2 else 0
        threshold = low4 + trigger_fraction * (high3 - low4)
    else:
        high0, low_a, high_b, low_c = p
        valid = low_a < high_b < high0 and low_c < low_a
        ratio = (high_b - low_a) / (high0 - low_a) if high0 > low_a else 0
        threshold = low_c + trigger_fraction * (high_b - low_c)
    if not valid or not 0.30 <= ratio <= 0.80:
        return None
    return direction * threshold, recent[-1][2]


def correction_signals(bars: list[dict], pattern: str, wing: int,
                       deviation_pct: float, trigger_pct: float) -> tuple[list[int], list[int]]:
    """Signals use only pivots confirmed *before* the signal candle closes."""
    if pattern not in ("wave2", "wave4", "abc") or trigger_pct not in (25, 50):
        raise ValueError("unknown Elliott proxy or trigger")
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    points: list[tuple[str, float, int]] = []
    pending = iter(confirmed_pivots(bars, wing, deviation_pct))
    next_pivot = next(pending, None)
    used = {1: -1, -1: -1}
    for i in range(1, n):
        previous, close = bars[i - 1]["close"], bars[i]["close"]
        for direction in (1, -1):
            candidate = _candidate(points, pattern, direction, trigger_pct / 100)
            if candidate is None:
                continue
            threshold, confirmed_at = candidate
            crossed = (direction * previous <= direction * threshold < direction * close)
            already_recovered = (i == confirmed_at + 1 and
                                 direction * close > direction * threshold)
            if (i - confirmed_at <= 20 and used[direction] != confirmed_at and
                    (crossed or already_recovered)):
                entries[i] = direction
                used[direction] = confirmed_at
                break
        latest_low = next((p[1] for p in reversed(points) if p[0] == "low"), None)
        latest_high = next((p[1] for p in reversed(points) if p[0] == "high"), None)
        if latest_low is not None and close < latest_low:
            exits[i] = -1
        elif latest_high is not None and close > latest_high:
            exits[i] = 1
        while next_pivot is not None and next_pivot[0] == i:
            confirmed, _, pivot_side, price = next_pivot
            if points and points[-1][0] == pivot_side:
                points[-1] = (pivot_side, price, confirmed)
            else:
                points.append((pivot_side, price, confirmed))
                if len(points) > 8:
                    del points[0]
            next_pivot = next(pending, None)
    return entries, exits
