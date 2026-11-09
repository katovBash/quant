"""Causal Band-ZigZag extreme-stall entry hypotheses.

The first number on the source chart is the current ZigZag leg length divided
by the previous leg length. This adaptation uses completed-bar BB20 pivots;
it does not claim parity with Trendoscope's imported sticky/adaptive bands.
"""

from __future__ import annotations

import math


def band_events(bars: list[dict]):
    result = []
    closes = [float(item["close"]) for item in bars]
    for i, bar in enumerate(bars):
        if i < 19:
            result.append((False, False))
            continue
        values = closes[i - 19:i + 1]
        middle = sum(values) / 20
        std = math.sqrt(sum((value - middle) ** 2 for value in values) / 20)
        result.append((float(bar["high"]) >= middle + 2 * std,
                       float(bar["low"]) <= middle - 2 * std))
    return result


def signal_factory(variant: str, bars: list[dict], events=None):
    # bb20__r100__s2__close: 100% of the previous leg, two completed
    # candles without a new extreme, then a close in the reverse direction.
    _, ratio_code, stall_code, confirmation = variant.split("__")
    threshold = {"r0": 0.0, "r100": 1.0, "r150": 1.5}[ratio_code]
    stale_bars = int(stall_code[1:])
    if confirmation not in ("close", "break") or stale_bars not in (1, 2, 3):
        raise ValueError(variant)
    events = events if events is not None else band_events(bars)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    last_side = 0
    pivot_bar = -1
    pivot_price = 0.0
    prior_price = None
    prior_prior_price = None
    used_pivot = -1
    for i, bar in enumerate(bars):
        high_touch, low_touch = events[i]
        if high_touch != low_touch:
            new_side = 1 if high_touch else -1
            price = float(bar["high"] if high_touch else bar["low"])
            if new_side != last_side:
                prior_prior_price, prior_price = prior_price, (pivot_price if last_side else None)
                last_side, pivot_bar, pivot_price = new_side, i, price
            elif (new_side == 1 and price > pivot_price) or (new_side == -1 and price < pivot_price):
                pivot_bar, pivot_price = i, price
        if last_side == 0 or pivot_bar < 0 or i - pivot_bar != stale_bars:
            continue
        ratio = 0.0
        if prior_price is not None and prior_prior_price is not None:
            denominator = abs(prior_price - prior_prior_price)
            if denominator > 0:
                ratio = abs(pivot_price - prior_price) / denominator
        if ratio < threshold or used_pivot == pivot_bar or i == 0:
            continue
        previous = bars[i - 1]
        if confirmation == "close":
            long_ok = float(bar["close"]) > float(bar["open"]) and float(bar["close"]) > float(previous["close"])
            short_ok = float(bar["close"]) < float(bar["open"]) and float(bar["close"]) < float(previous["close"])
        else:
            long_ok = float(bar["close"]) > float(previous["high"])
            short_ok = float(bar["close"]) < float(previous["low"])
        direction = (1 if last_side == -1 and long_ok else
                     -1 if last_side == 1 and short_ok else 0)
        if direction:
            entries[i] = direction
            used_pivot = pivot_bar
    # The opposite entry reverses the independent account at the next open.
    return entries, exits


def context_factory(_symbol: str, _timeframe: str):
    saved_events = None

    def factory(variant: str, bars: list[dict]):
        nonlocal saved_events
        if saved_events is None:
            saved_events = band_events(bars)
        return signal_factory(variant, bars, saved_events)

    return factory
