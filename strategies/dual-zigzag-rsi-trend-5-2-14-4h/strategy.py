"""Fixed 4H causal price/RSI swing rule selected by the frozen experiment."""

from __future__ import annotations

import importlib.util
from pathlib import Path

STRATEGY_ID = "dual-zigzag-rsi-trend-5-2-14-4h"
TIMEFRAME = "4H"
VARIANT = "dual_5_2_14_trend-opp"
PAPER_SYMBOLS = ["RAGR", "ALRS", "MTLR", "PLZL", "SFIN", "WUSH", "NLMK"]

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/dual-zigzag/price-oscillator-swings/run.py"
spec = importlib.util.spec_from_file_location("dual_zigzag_frozen_signals", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("frozen signal module unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def signal(completed_4h_bars: list[dict]) -> str | None:
    """Return the latest close-time event; paper fills at the following open."""
    if len(completed_4h_bars) < 30:
        return None
    entries, _ = module.factory("", TIMEFRAME)(VARIANT, completed_4h_bars)
    event = entries[-1]
    return "long" if event > 0 else "short" if event < 0 else None
