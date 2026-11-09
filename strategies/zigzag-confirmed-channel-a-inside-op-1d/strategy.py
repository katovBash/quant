"""Fixed daily ZigZag parallel-channel bounce selected by the full experiment."""

from __future__ import annotations

from src.research.zigzag_signals import confirmed_channel_bounce_signals

STRATEGY_ID = "zigzag-confirmed-channel-a-inside-op-1d"
TIMEFRAME = "1D"
USES_POSITION = True
PAPER_SYMBOLS = ["ASTR"]
WING = 3
DEVIATION_PCT = 2.0
ZONE_PCT = 0.5
MAX_AGE = 80


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    if len(bars) < 16:
        return None
    entries, exits = confirmed_channel_bounce_signals(
        bars, WING, DEVIATION_PCT, ZONE_PCT, MAX_AGE,
        exit_mode="opposite_line", confirm_mode="inside")
    if entries[-1] > 0:
        return "long"
    if entries[-1] < 0:
        return "short"
    if position > 0 and exits[-1] < 0:
        return "flat"
    if position < 0 and exits[-1] > 0:
        return "flat"
    return None
