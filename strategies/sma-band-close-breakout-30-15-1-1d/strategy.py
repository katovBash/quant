"""Fixed daily SMA Bollinger-band breakout selected by the experiment."""

from __future__ import annotations

from src.research.sma_band_close_breakout import signals_for_variant

STRATEGY_ID = "sma-band-close-breakout-30-15-1-1d"
TIMEFRAME = "1D"
VARIANT = "bb_30_15_1"
PAPER_SYMBOLS = ["POSI", "VKCO", "SMLT", "MGNT", "MSNG", "AFLT", "HYDR",
                 "PLZL", "UNAC", "VTBR", "SELG", "UGLD", "MAGN"]


def signal(bars: list[dict]) -> str | None:
    """Return a direction only on the latest completed daily bar."""
    if len(bars) < 31:
        return None
    entries, _ = signals_for_variant(VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
