"""Fixed 4H third-touch breakout with a 5% target for virtual accounts."""

from __future__ import annotations

from src.research.zigzag_signals import third_touch_signals

STRATEGY_ID = "zigzag-third-touch-a-c-x-t5-4h"
TIMEFRAME = "4H"
USES_POSITION = True
PAPER_SYMBOLS = ["AFKS", "SFIN", "HEAD", "TATNP", "RTKM", "ASTR", "TATN", "FESH", "X5"]
WING = 3
DEVIATION_PCT = 2.0
ZONE_PCT = 0.5
MAX_AGE = 50


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    """Match completed-bar research events; paper execution occurs at next open."""
    if len(bars) < 2 * WING + 2:
        return None
    entries, exits = third_touch_signals(
        bars, WING, DEVIATION_PCT, ZONE_PCT, MAX_AGE, "breakout",
        exit_mode="tp_5")
    if entries[-1] > 0:
        return "long"
    if entries[-1] < 0:
        return "short"
    if position > 0 and exits[-1] < 0:
        return "flat"
    if position < 0 and exits[-1] > 0:
        return "flat"
    return None
