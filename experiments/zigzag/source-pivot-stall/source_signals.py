"""Past-only port of the supplied Band-ZigZag's default BB pivot updates.

The sticky BB rule comes from HeWhoMustNotBeNamed/ta/1's published source.
Only the source script's default SMA20, multiplier 2, sticky/adaptive settings
are ported here. Its Keltner/Donchian and alternative MA settings are not.
"""

from __future__ import annotations

import math


def pivots_by_bar(bars: list[dict]) -> list[dict]:
    closes = [float(bar["close"]) for bar in bars]
    points: list[dict] = []  # newest first, same sign convention as source Pine
    records: list[dict] = []
    prior_sticky_upper = prior_sticky_lower = None
    prior_adaptive_upper = prior_adaptive_lower = None
    prior_high = prior_low = None
    current_dir = 0

    def add_pivot(side: int, index: int, high: float, low: float) -> bool:
        price = high if side > 0 else low
        if not points:
            points.insert(0, {"side": side, "bar": index, "price": price})
            return True
        previous = points[0]
        if previous["side"] != side:
            points.insert(0, {"side": side, "bar": index, "price": price})
            if len(points) > 15:
                points.pop()
            return True
        if previous["price"] * side < price * side:
            points.pop(0)
            points.insert(0, {"side": side, "bar": index, "price": price})
            return True
        return False

    for index, bar in enumerate(bars):
        high, low = float(bar["high"]), float(bar["low"])
        if index < 19:
            records.append({"pivot_bar": -1, "side": 0, "pivot_price": None})
            prior_high, prior_low = high, low
            continue
        window = closes[index - 19:index + 1]
        middle = sum(window) / 20
        deviation = math.sqrt(sum((price - middle) ** 2 for price in window) / 20)
        raw_upper, raw_lower = middle + 2 * deviation, middle - 2 * deviation
        breakout = (prior_sticky_upper is not None and
                    (prior_high >= prior_sticky_upper or prior_low <= prior_sticky_lower))
        sticky_upper = raw_upper if breakout or prior_sticky_upper is None else prior_sticky_upper
        sticky_lower = raw_lower if breakout or prior_sticky_lower is None else prior_sticky_lower

        # In the source, currentDir is read before this bar's add_pivots call.
        if len(points) > 1:
            current_dir = points[0]["side"]
        adaptive_upper = (sticky_upper if current_dir >= 0 or prior_adaptive_upper is None
                          else min(sticky_upper, prior_adaptive_upper))
        adaptive_lower = (sticky_lower if current_dir <= 0 or prior_adaptive_lower is None
                          else max(sticky_lower, prior_adaptive_lower))
        high_touch, low_touch = high >= adaptive_upper, low <= adaptive_lower

        if not points:
            if high_touch:
                add_pivot(1, index, high, low)
            if low_touch:
                add_pivot(-1, index, high, low)
        else:
            old_side = points[0]["side"]
            if (high_touch and old_side == 1) or (low_touch and old_side == -1):
                add_pivot(old_side, index, high, low)
            if (high_touch and old_side == -1) or (low_touch and old_side == 1):
                add_pivot(-old_side, index, high, low)

        records.append({"pivot_bar": points[0]["bar"] if len(points) > 1 else -1,
                        "side": points[0]["side"] if len(points) > 1 else 0,
                        "pivot_price": points[0]["price"] if len(points) > 1 else None})
        prior_high, prior_low = high, low
        prior_sticky_upper, prior_sticky_lower = sticky_upper, sticky_lower
        prior_adaptive_upper, prior_adaptive_lower = adaptive_upper, adaptive_lower
    return records


def signals_for_variant(variant: str, bars: list[dict], records: list[dict] | None = None):
    if not variant.startswith("pivot__d"):
        raise ValueError(variant)
    delay = int(variant.removeprefix("pivot__d"))
    if not 0 <= delay <= 30:
        raise ValueError(variant)
    records = records if records is not None else pivots_by_bar(bars)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    for index, point in enumerate(records):
        if point["side"] and index - point["pivot_bar"] == delay:
            entries[index] = -point["side"]
    return entries, exits


def context_factory(_symbol: str, _timeframe: str):
    cached = None

    def factory(variant: str, bars: list[dict]):
        nonlocal cached
        if cached is None:
            cached = pivots_by_bar(bars)
        return signals_for_variant(variant, bars, cached)

    return factory
