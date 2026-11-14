"""Close-confirmed SMA Bollinger-band crossing; next-bar execution is external."""

from __future__ import annotations

import math


def signals_for_variant(variant: str, bars: list[dict]) -> tuple[list[int], list[int]]:
    # bb_{length}_{sigma_x10}_{confirm_bars}; e.g. bb_20_20_1.
    _, length_text, sigma_text, count_text = variant.split("_")
    length, sigma, confirmation = int(length_text), int(sigma_text) / 10, int(count_text)
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    closes = [float(bar["close"]) for bar in bars]
    total = squares = 0.0
    previous_upper = previous_lower = math.nan
    above_count = below_count = 0
    for i, close in enumerate(closes):
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
        crossed_up = i > length - 1 and close > upper and closes[i - 1] <= previous_upper
        crossed_down = i > length - 1 and close < lower and closes[i - 1] >= previous_lower
        above_count = (1 if crossed_up else above_count + 1 if above_count and close > upper else 0)
        below_count = (1 if crossed_down else below_count + 1 if below_count and close < lower else 0)
        if above_count == confirmation:
            entries[i] = 1
        elif below_count == confirmation:
            entries[i] = -1
        previous_upper, previous_lower = upper, lower
    return entries, exits
