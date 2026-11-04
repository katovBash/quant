"""Frozen 4H line-retest rule used by review scripts and paper accounts."""

from __future__ import annotations

from src.research.ema_zone_lines import higher_lines, line_retest_signals
from src.research.standalone_grid import ema_level_signals


def events(bars: list[dict], hourly_bars: list[dict], *, wing: int,
           zone_atr: float) -> tuple[list[int], list[int]]:
    """Return entry and opposite-EMA exit events from completed candles only."""
    if wing not in (1, 2) or zone_atr not in (0.5, 1.0):
        raise ValueError("rule parameters differ from reviewed variants")
    lines = higher_lines(bars, [], "4H", hourly=hourly_bars, wing=wing, max_age=60)
    return (line_retest_signals(bars, lines, zone_atr, "slope", bend_bars=1),
            ema_level_signals(bars, 25, 0.5))


def decision(bars: list[dict], hourly_bars: list[dict], position: int, *,
             wing: int, zone_atr: float) -> str | None:
    """One completed signal bar; paper runner queues execution on the next bar."""
    entries, exits = events(bars, hourly_bars, wing=wing, zone_atr=zone_atr)
    if not entries:
        return None
    if entries[-1] > 0:
        return "long"
    if entries[-1] < 0:
        return "short"
    if position > 0 and exits[-1] < 0 or position < 0 and exits[-1] > 0:
        return "flat"
    return None
