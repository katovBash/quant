"""Fixed weekly Band-ZigZag reversal rule selected from the frozen experiment.

The paper runner supplies completed daily candles. The order is emitted after
a completed weekly candle and the runner fills it at the next daily open.
"""

from __future__ import annotations

from src.research.band_zigzag_weekly import signals_for_variant

STRATEGY_ID = "zigzag-band-turn-two-closes-opposite-1w"
TIMEFRAME = "1W"
PAPER_SYMBOLS = ["SNGS", "NLMK", "HYDR", "PLZL", "MGNT", "MSNG",
                 "ROSN", "GAZP", "SELG", "SPBE", "SFIN", "VTBR"]
VARIANT = "bb20__two_closes__opposite"


def weekly_signal(weekly_bars: list[dict]) -> str | None:
    if len(weekly_bars) < 21:
        return None
    entries, _ = signals_for_variant(VARIANT, weekly_bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None


def signal(weekly_bars: list[dict]) -> str | None:
    """Signal for a finalized weekly series; used by the paper week transition."""
    return weekly_signal(weekly_bars)
