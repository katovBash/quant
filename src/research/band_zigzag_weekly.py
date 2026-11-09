"""Causal weekly Bollinger-band ZigZag and post-pivot trade signals.

This is a declared OHLC adaptation, not a port of Trendoscope's imported ta library.
The latest extreme can change; a past signal is never moved with it.
"""

from __future__ import annotations

import math


CONFIRMATIONS = ("first_close", "break_prev", "two_closes")
EXITS = ("opposite", "target5", "target8")


def band_events(bars: list[dict], length: int = 20, multiplier: float = 2.0):
    """Bollinger SMA and population deviation of completed weekly closes."""
    result = []
    for i, bar in enumerate(bars):
        if i < length - 1:
            result.append((False, False))
            continue
        values = [float(item["close"]) for item in bars[i - length + 1:i + 1]]
        middle = sum(values) / length
        deviation = math.sqrt(sum((value - middle) ** 2 for value in values) / length)
        upper, lower = middle + multiplier * deviation, middle - multiplier * deviation
        result.append((float(bar["high"]) >= upper, float(bar["low"]) <= lower))
    return result


def signals_for_variant(variant: str, bars: list[dict]):
    """Observe at weekly close; simulator fills entry/exit at next weekly open."""
    _, confirmation, exit_mode = variant.split("__")
    assert confirmation in CONFIRMATIONS and exit_mode in EXITS
    events = band_events(bars)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    side = 0
    pivot_bar = -1
    pivot_price = 0.0
    used_pivot = -1
    synthetic_position = 0
    synthetic_entry = 0.0
    for i, bar in enumerate(bars):
        # The signal from the previous completed week executes at this open.
        if i and entries[i - 1] and (synthetic_position == 0 or synthetic_position != entries[i - 1]):
            synthetic_position = entries[i - 1]
            synthetic_entry = float(bar["open"])
        elif i and exits[i - 1]:
            synthetic_position = 0
        high_event, low_event = events[i]
        # A bar spanning both bands is ambiguous: no new pivot or signal.
        if high_event != low_event:
            new_side = 1 if high_event else -1
            price = float(bar["high"] if new_side == 1 else bar["low"])
            if side != new_side or (new_side == 1 and price > pivot_price) or (new_side == -1 and price < pivot_price):
                side, pivot_bar, pivot_price = new_side, i, price
        if i < 2 or side == 0 or pivot_bar >= i or i - pivot_bar > 8:
            continue
        previous = bars[i - 1]
        rising = float(bar["close"]) > float(previous["close"])
        falling = float(bar["close"]) < float(previous["close"])
        if confirmation == "first_close":
            long_ok = rising and float(bar["close"]) > float(bar["open"])
            short_ok = falling and float(bar["close"]) < float(bar["open"])
        elif confirmation == "break_prev":
            long_ok = float(bar["close"]) > float(previous["high"])
            short_ok = float(bar["close"]) < float(previous["low"])
        else:
            long_ok = rising and float(previous["close"]) > float(bars[i - 2]["close"])
            short_ok = falling and float(previous["close"]) < float(bars[i - 2]["close"])
        proposed = (1 if side == -1 and long_ok else -1 if side == 1 and short_ok else 0)
        if proposed and used_pivot != pivot_bar and synthetic_position != proposed:
            entries[i] = proposed
            used_pivot = pivot_bar
        if exit_mode != "opposite" and synthetic_position and not entries[i]:
            target = 1.05 if exit_mode == "target5" else 1.08
            if synthetic_position > 0 and float(bar["high"]) >= synthetic_entry * target:
                exits[i] = -1
            if synthetic_position < 0 and float(bar["low"]) <= synthetic_entry * (2 - target):
                exits[i] = 1
    return entries, exits
