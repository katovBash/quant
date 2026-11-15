"""Causal interpretation of repeated Bollinger-band hits after midline returns.

The published Trendoscope description specifies the band-hit state, but not a
complete trading system. Entry and exit rules here are preregistered research
choices, not a reproduction of the author's private trading record.
"""

from __future__ import annotations

import math


def signals_for_variant(variant: str, bars: list[dict]) -> tuple[list[int], list[int]]:
    # bh_{length}_20_{required_hits}_{touch|cross}_{opp|mid}
    _, length_text, sigma_text, required_text, reset, exit_mode = variant.split("_")
    length = int(length_text)
    sigma = int(sigma_text) / 10
    required_hits = int(required_text)
    if reset not in ("touch", "cross") or exit_mode not in ("opp", "mid"):
        raise ValueError(f"unknown band-hit variant: {variant}")
    closes = [float(bar["close"]) for bar in bars]
    entries, exits = [0] * len(bars), [0] * len(bars)
    total = squares = 0.0
    last_side = hit_count = 0
    returned_to_middle = False
    previous_middle = math.nan
    for i, (bar, close) in enumerate(zip(bars, closes)):
        total += close
        squares += close * close
        if i >= length:
            old = closes[i - length]
            total -= old
            squares -= old * old
        if i < length - 1:
            continue
        middle = total / length
        deviation = math.sqrt(max(0.0, squares / length - middle * middle))
        upper, lower = middle + sigma * deviation, middle - sigma * deviation
        side = 1 if close > upper else -1 if close < lower else 0
        if side:
            if side != last_side:
                last_side, hit_count = side, 1
                returned_to_middle = False
            elif returned_to_middle:
                hit_count += 1
                returned_to_middle = False
            else:
                side = 0  # Consecutive closes outside the band count as one hit.
            if side and hit_count >= required_hits:
                entries[i] = side
        elif last_side:
            if reset == "touch":
                returned_to_middle |= float(bar["low"]) <= middle <= float(bar["high"])
            elif last_side > 0:
                returned_to_middle |= close <= middle
            else:
                returned_to_middle |= close >= middle
        if exit_mode == "mid" and i > length - 1:
            if close < middle and closes[i - 1] >= previous_middle:
                exits[i] = -1  # Exit a long position at next open.
            elif close > middle and closes[i - 1] <= previous_middle:
                exits[i] = 1  # Exit a short position at next open.
        previous_middle = middle
    return entries, exits
