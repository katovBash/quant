"""Past-only confirmed ZigZag pivots and level-breakout signals."""

from __future__ import annotations


def confirmed_pivots(bars: list[dict], wing: int, deviation_pct: float):
    """Yield (confirmation index, pivot index, side, price) without backdating events."""
    if wing < 1 or deviation_pct <= 0:
        raise ValueError("positive wing and reversal deviation required")
    last_side = None
    last_price = None
    for i in range(2 * wing, len(bars)):
        center = i - wing
        previous = bars[center - wing:center]
        following = bars[center + 1:i + 1]
        high = bars[center]["high"]
        low = bars[center]["low"]
        high_ok = high > max(bar["high"] for bar in previous) and high >= max(
            bar["high"] for bar in following)
        low_ok = low < min(bar["low"] for bar in previous) and low <= min(
            bar["low"] for bar in following)
        for side, price, valid in (("high", high, high_ok), ("low", low, low_ok)):
            if not valid:
                continue
            if last_side is None or (side == last_side and
                                     (price > last_price if side == "high" else price < last_price)):
                last_side, last_price = side, price
                yield i, center, side, price
            elif side != last_side and 100 * abs(price / last_price - 1) >= deviation_pct:
                last_side, last_price = side, price
                yield i, center, side, price


def breakout_signals(bars: list[dict], wing: int, deviation_pct: float):
    """Signal on close after crossing a level known before the current bar."""
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    last_high = last_low = None
    for i in range(1, n):
        close, previous_close = bars[i]["close"], bars[i - 1]["close"]
        if last_high is not None and previous_close <= last_high < close:
            entries[i] = 1
        elif last_low is not None and previous_close >= last_low > close:
            entries[i] = -1
        if last_low is not None and close < last_low:
            exits[i] = -1
        elif last_high is not None and close > last_high:
            exits[i] = 1
        while pending is not None and pending[0] == i:
            _, _, side, price = pending
            if side == "high":
                last_high = price
            else:
                last_low = price
            pending = next(pivots, None)
    return entries, exits


def retest_signals(bars: list[dict], wing: int, deviation_pct: float,
                   zone_pct: float):
    """One entry on the first post-breakout retest of a known pivot level."""
    if zone_pct < 0:
        raise ValueError("zone_pct must be nonnegative")
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    last_high = last_low = None
    armed_high = armed_low = None
    armed_high_at = armed_low_at = -1
    for i in range(1, n):
        bar, previous_close = bars[i], bars[i - 1]["close"]
        close = bar["close"]
        if armed_high is not None and i > armed_high_at and (
                bar["low"] <= armed_high * (1 + zone_pct / 100)
                and bar["low"] >= armed_high * (1 - zone_pct / 100)
                and close > armed_high):
            entries[i] = 1
            armed_high = None
        elif armed_low is not None and i > armed_low_at and (
                bar["high"] >= armed_low * (1 - zone_pct / 100)
                and bar["high"] <= armed_low * (1 + zone_pct / 100)
                and close < armed_low):
            entries[i] = -1
            armed_low = None
        if last_high is not None and close < last_high:
            exits[i] = -1
        elif last_low is not None and close > last_low:
            exits[i] = 1
        if last_high is not None and previous_close <= last_high < close:
            armed_high, armed_high_at = last_high, i
            armed_low = None
        if last_low is not None and previous_close >= last_low > close:
            armed_low, armed_low_at = last_low, i
            armed_high = None
        while pending is not None and pending[0] == i:
            _, _, side, price = pending
            if side == "high":
                last_high = price
                armed_high = None
            else:
                last_low = price
                armed_low = None
            pending = next(pivots, None)
    return entries, exits


def _line(points: list[tuple[int, float]], at: int):
    if len(points) < 2:
        return None
    (i0, p0), (i1, p1) = points[-2:]
    if i1 <= i0:
        return None
    return p1 + (p1 - p0) * (at - i1) / (i1 - i0)


def trendline_signals(bars: list[dict], wing: int, deviation_pct: float,
                      max_age: int):
    """Cross the line through two already confirmed same-side pivots."""
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    highs, lows = [], []
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    for i in range(1, n):
        high_line = _line(highs, i)
        low_line = _line(lows, i)
        high_previous = _line(highs, i - 1)
        low_previous = _line(lows, i - 1)
        if (high_line is not None and high_previous is not None
                and i - highs[-1][0] <= max_age and high_line > 0
                and bars[i - 1]["close"] <= high_previous
                and bars[i]["close"] > high_line):
            entries[i] = 1
        elif (low_line is not None and low_previous is not None
              and i - lows[-1][0] <= max_age and low_line > 0
              and bars[i - 1]["close"] >= low_previous
              and bars[i]["close"] < low_line):
            entries[i] = -1
        exits[i] = entries[i]
        while pending is not None and pending[0] == i:
            _, center, side, price = pending
            (highs if side == "high" else lows).append((center, price))
            pending = next(pivots, None)
    return entries, exits


def compression_signals(bars: list[dict], wing: int, deviation_pct: float,
                        min_narrowing_pct: float):
    """Break a converging two-high/two-low pivot triangle after confirmation."""
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    highs, lows = [], []
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    for i in range(1, n):
        if len(highs) >= 2 and len(lows) >= 2:
            start = max(highs[-2][0], lows[-2][0])
            upper_start, lower_start = _line(highs, start), _line(lows, start)
            upper, lower = _line(highs, i), _line(lows, i)
            upper_previous, lower_previous = _line(highs, i - 1), _line(lows, i - 1)
            initial_width = upper_start - lower_start
            width = upper - lower
            converging = highs[-1][1] < highs[-2][1] and lows[-1][1] > lows[-2][1]
            if (converging and initial_width > 0 and width > 0 and upper > 0
                    and i - max(highs[-1][0], lows[-1][0]) <= 100
                    and 100 * (1 - width / initial_width) >= min_narrowing_pct):
                if bars[i - 1]["close"] <= upper_previous and bars[i]["close"] > upper:
                    entries[i] = 1
                elif bars[i - 1]["close"] >= lower_previous and bars[i]["close"] < lower:
                    entries[i] = -1
                exits[i] = entries[i]
        while pending is not None and pending[0] == i:
            _, center, side, price = pending
            (highs if side == "high" else lows).append((center, price))
            pending = next(pivots, None)
    return entries, exits
