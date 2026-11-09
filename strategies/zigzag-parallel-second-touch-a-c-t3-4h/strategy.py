"""Fixed parallel-channel second-contact rule for virtual SFIN account."""

from __future__ import annotations

from src.research.zigzag_signals import parallel_second_touch_signals

STRATEGY_ID = "zigzag-parallel-second-touch-a-c-t3-4h"
TIMEFRAME = "4H"
USES_POSITION = True
PAPER_SYMBOLS = ["SFIN"]
WING = 3
DEVIATION_PCT = 2.0
ZONE_PCT = 0.5
MAX_AGE = 50


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    if len(bars) < 2 * WING + 2:
        return None
    entries, exits = parallel_second_touch_signals(
        bars, WING, DEVIATION_PCT, ZONE_PCT, MAX_AGE, exit_mode="tp_3")
    if entries[-1] > 0:
        return "long"
    if entries[-1] < 0:
        return "short"
    if position > 0 and exits[-1] < 0:
        return "flat"
    if position < 0 and exits[-1] > 0:
        return "flat"
    return None
