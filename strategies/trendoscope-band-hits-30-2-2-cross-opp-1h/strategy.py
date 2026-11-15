"""Fixed 1H repeated Bollinger-band hit rule from the frozen experiment."""

from __future__ import annotations

from src.research.trendoscope_band_hits import signals_for_variant

STRATEGY_ID = "trendoscope-band-hits-30-2-2-cross-opp-1h"
TIMEFRAME = "1H"
VARIANT = "bh_30_20_2_cross_opp"
PAPER_SYMBOLS = ["PHOR", "MAGN", "TATNP"]


def signal(bars: list[dict]) -> str | None:
    if len(bars) < 31:
        return None
    entries, _ = signals_for_variant(VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
