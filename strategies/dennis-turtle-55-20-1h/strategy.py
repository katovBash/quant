"""Frozen close-confirmed Turtle 55/20 signal for 1H paper accounts."""

from __future__ import annotations

STRATEGY_ID = "dennis-turtle-55-20-1h"
TIMEFRAME = "1H"
PAPER_SYMBOLS = ["SFIN", "WUSH", "MTLR", "EUTR", "NLMK", "LKOH", "SVCB", "IRKT", "MRKC", "ROSN"]


def signal(bars: list[dict], *, position: int = 0) -> str | None:
    """Act on a completed bar; the fleet queues execution for its next observation."""
    if len(bars) < 56:
        return None
    current = bars[-1]["close"]
    prior_entry = bars[-56:-1]
    prior_exit = bars[-21:-1]
    if current > max(bar["high"] for bar in prior_entry):
        return "long"
    if current < min(bar["low"] for bar in prior_entry):
        return "short"
    if position > 0 and current < min(bar["low"] for bar in prior_exit):
        return "flat"
    if position < 0 and current > max(bar["high"] for bar in prior_exit):
        return "flat"
    return None
