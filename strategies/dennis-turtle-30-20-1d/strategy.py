"""Frozen close-confirmed Turtle 30/20 signal for 1D virtual accounts."""

from __future__ import annotations

STRATEGY_ID = "dennis-turtle-30-20-1d"
TIMEFRAME = "1D"
PAPER_SYMBOLS = ["VSEH", "WUSH", "POSI", "LENT", "VKCO", "NLMK", "BELU", "ENPG", "MSNG", "GMKN"]


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    """Use only completed bars; execution is queued for the next observation."""
    if len(bars) < 31:
        return None
    close = bars[-1]["close"]
    entry = bars[-31:-1]
    exit_bars = bars[-21:-1]
    if close > max(bar["high"] for bar in entry):
        return "long"
    if close < min(bar["low"] for bar in entry):
        return "short"
    if position > 0 and close < min(bar["low"] for bar in exit_bars):
        return "flat"
    if position < 0 and close > max(bar["high"] for bar in exit_bars):
        return "flat"
    return None
