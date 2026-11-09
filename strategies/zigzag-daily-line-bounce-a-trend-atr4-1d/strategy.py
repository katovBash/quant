"""Fixed daily support/resistance bounce with 4 × ATR14 target."""

from __future__ import annotations

from src.research.zigzag_signals import third_touch_signals

STRATEGY_ID = "zigzag-daily-line-bounce-a-trend-atr4-1d"
TIMEFRAME = "1D"
USES_POSITION = True
PAPER_SYMBOLS = ["CBOM", "ENPG", "GMKN", "RUAL", "SMLT", "WUSH", "RAGR", "SFIN"]
WING = 3
DEVIATION_PCT = 2.0
ZONE_PCT = 0.5
MAX_AGE = 50


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    if len(bars) < 16:
        return None
    entries, exits = third_touch_signals(
        bars, WING, DEVIATION_PCT, ZONE_PCT, MAX_AGE, "bounce",
        exit_mode="tp_atr_4", slope_mode="trend")
    if entries[-1] > 0:
        return "long"
    if entries[-1] < 0:
        return "short"
    if position > 0 and exits[-1] < 0:
        return "flat"
    if position < 0 and exits[-1] > 0:
        return "flat"
    return None
