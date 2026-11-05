"""Fixed, close-confirmed ZigZag 5/6 breakout for 1D virtual accounts."""

from __future__ import annotations

from src.research.zigzag_signals import confirmed_pivots

STRATEGY_ID = "zigzag-confirmed-breakout-5-6-1d"
TIMEFRAME = "1D"
USES_POSITION = True
PAPER_SYMBOLS = ["MTSS", "VSEH", "WUSH", "VKCO", "RTKM", "SNGSP",
                 "NVTK", "POSI", "MAGN", "LENT"]
WING = 5
DEVIATION_PCT = 6.0


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    """Act on a finished close using only pivots confirmed before this bar."""
    if len(bars) < 2 * WING + 2:
        return None
    index = len(bars) - 1
    known_high = known_low = None
    for confirmed_at, _, side, price in confirmed_pivots(bars, WING, DEVIATION_PCT):
        if confirmed_at >= index:
            break
        if side == "high":
            known_high = price
        else:
            known_low = price
    close = bars[index]["close"]
    previous_close = bars[index - 1]["close"]
    if known_high is not None and previous_close <= known_high < close:
        return "long"
    if known_low is not None and previous_close >= known_low > close:
        return "short"
    if position > 0 and known_low is not None and close < known_low:
        return "flat"
    if position < 0 and known_high is not None and close > known_high:
        return "flat"
    return None
