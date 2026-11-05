"""Causal session VWAP deviation and fixed-bar exit signals for 1H bars."""

from __future__ import annotations

from collections import deque


def _atr14(bars: list[dict]) -> list[float | None]:
    result = [None] * len(bars)
    recent: deque[float] = deque()
    total = 0.0
    for i, bar in enumerate(bars):
        previous_close = bars[i - 1]["close"] if i else bar["close"]
        tr = max(bar["high"] - bar["low"], abs(bar["high"] - previous_close),
                 abs(bar["low"] - previous_close))
        recent.append(tr)
        total += tr
        if len(recent) > 14:
            total -= recent.popleft()
        if len(recent) == 14:
            result[i] = total / 14
    return result


def session_vwap(bars: list[dict]) -> tuple[list[float | None], list[int]]:
    values: list[float | None] = [None] * len(bars)
    counts = [0] * len(bars)
    current_day = None
    amount = volume = 0.0
    count = 0
    for i, bar in enumerate(bars):
        day = bar["ts"][:10]
        if day != current_day:
            current_day, amount, volume, count = day, 0.0, 0.0, 0
        traded = float(bar.get("volume") or 0)
        typical = (bar["high"] + bar["low"] + bar["close"]) / 3
        amount += typical * traded
        volume += traded
        count += 1
        counts[i] = count
        values[i] = amount / volume if volume > 0 else None
    return values, counts


def signals(bars: list[dict], deviation_atr: float, hold_bars: int) -> tuple[list[int], list[int]]:
    if deviation_atr <= 0 or hold_bars < 1:
        raise ValueError("positive deviation and holding period required")
    atr = _atr14(bars)
    vwap, session_count = session_vwap(bars)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    previous_long = previous_short = False
    previous_day = None
    active_until = -1
    for i, bar in enumerate(bars):
        day = bar["ts"][:10]
        if day != previous_day:
            previous_long = previous_short = False
            previous_day = day
        valid = session_count[i] >= 3 and atr[i] is not None and vwap[i] is not None
        long_outside = bool(valid and bar["close"] < vwap[i] - deviation_atr * atr[i])
        short_outside = bool(valid and bar["close"] > vwap[i] + deviation_atr * atr[i])
        if i > active_until:
            direction = (1 if long_outside and not previous_long and not short_outside else
                         -1 if short_outside and not previous_short and not long_outside else 0)
            if direction:
                entries[i] = direction
                active_until = i + hold_bars
                if active_until < len(bars):
                    exits[active_until] = -direction
        previous_long, previous_short = long_outside, short_outside
    return entries, exits
