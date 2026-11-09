"""Fixed 1H third-touch breakout, opposite-signal exit, for virtual accounts."""

from __future__ import annotations

from src.research.zigzag_signals import third_touch_signals

STRATEGY_ID = "zigzag-third-touch-b-c-x-op-1h"
TIMEFRAME = "1H"
PAPER_SYMBOLS = ["ENPG", "VSEH", "AFLT", "RNFT", "NLMK", "POSI", "CBOM",
                 "SGZH", "SELG", "VTBR", "LKOH"]
WING = 5
DEVIATION_PCT = 4.0
ZONE_PCT = 1.0
MAX_AGE = 100


def signal(bars: list[dict]) -> str | None:
    """Return the close-confirmed signal; the paper runner fills at next open."""
    if len(bars) < 2 * WING + 2:
        return None
    entries, _ = third_touch_signals(
        bars, WING, DEVIATION_PCT, ZONE_PCT, MAX_AGE, "breakout",
        exit_mode="opposite_signal")
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
