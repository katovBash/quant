"""Causal Turtle signals for a frozen entry/exit grid."""

from __future__ import annotations

from collections import deque


def prior_extrema(bars: list[dict], lengths: set[int]) -> dict[int, tuple[list[float | None], list[float | None]]]:
    """Return high/low of the preceding N completed bars, excluding this bar."""
    result = {}
    for length in sorted(lengths):
        highs = [None] * len(bars)
        lows = [None] * len(bars)
        high_queue: deque[int] = deque()
        low_queue: deque[int] = deque()
        for index in range(len(bars)):
            previous = index - 1
            if previous >= 0:
                high = bars[previous]["high"]
                low = bars[previous]["low"]
                while high_queue and bars[high_queue[-1]]["high"] <= high:
                    high_queue.pop()
                high_queue.append(previous)
                while low_queue and bars[low_queue[-1]]["low"] >= low:
                    low_queue.pop()
                low_queue.append(previous)
            cutoff = index - length
            while high_queue and high_queue[0] < cutoff:
                high_queue.popleft()
            while low_queue and low_queue[0] < cutoff:
                low_queue.popleft()
            if index >= length:
                highs[index] = bars[high_queue[0]]["high"]
                lows[index] = bars[low_queue[0]]["low"]
        result[length] = highs, lows
    return result


def turtle_from_extrema(bars: list[dict], entry: int, exit_length: int,
                        extrema: dict[int, tuple[list[float | None], list[float | None]]]
                        ) -> tuple[list[int], list[int]]:
    signals = [0] * len(bars)
    exits = [0] * len(bars)
    entry_high, entry_low = extrema[entry]
    exit_high, exit_low = extrema[exit_length]
    for index in range(max(entry, exit_length), len(bars)):
        close = bars[index]["close"]
        if close > entry_high[index]:
            signals[index] = 1
        elif close < entry_low[index]:
            signals[index] = -1
        if close < exit_low[index]:
            exits[index] = -1
        elif close > exit_high[index]:
            exits[index] = 1
    return signals, exits


def entry_only_from_extrema(bars: list[dict], entry: int,
                            extrema: dict[int, tuple[list[float | None], list[float | None]]]
                            ) -> tuple[list[int], list[int]]:
    """Only entry-channel breakouts; reverse on the opposite entry breakout."""
    signals = [0] * len(bars)
    upper, lower = extrema[entry]
    for index in range(entry, len(bars)):
        close = bars[index]["close"]
        if close > upper[index]:
            signals[index] = 1
        elif close < lower[index]:
            signals[index] = -1
    return signals, [0] * len(bars)


def buy_hold(bars: list[dict], start: str) -> tuple[list[int], list[int]]:
    signals = [0] * len(bars)
    for index in range(33, len(bars)):
        if bars[index]["ts"][:10] >= start:
            signals[index - 1] = 1
            break
    return signals, [0] * len(bars)
