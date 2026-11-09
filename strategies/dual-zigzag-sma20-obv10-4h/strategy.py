"""Fixed 4H SMA20 Dual ZigZag with 10-bar OBV flow entry confirmation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

STRATEGY_ID = "dual-zigzag-sma20-obv10-4h"
TIMEFRAME = "4H"
VARIANT = "combined_10"
PAPER_SYMBOLS = ["MTLR", "VKCO", "NLMK", "WUSH", "GAZP", "PLZL", "SFIN", "ALRS", "SELG"]
USES_POSITION = True

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/double-indicator/dual-zigzag-sma-obv-confirmation/run.py"
spec = importlib.util.spec_from_file_location("frozen_dual_zigzag_obv", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("frozen OBV experiment unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def events(completed_4h_bars: list[dict]) -> tuple[int, int]:
    if len(completed_4h_bars) < 70:
        return 0, 0
    accepted, raw_exit = module.factory("", TIMEFRAME)(VARIANT, completed_4h_bars)
    return accepted[-1], raw_exit[-1]


def signal(completed_4h_bars: list[dict], *, position: int = 0) -> str | None:
    """Return a close-time event; the paper runner fills on a subsequent bar."""
    accepted, raw_exit = events(completed_4h_bars)
    if accepted > 0:
        return "long"
    if accepted < 0:
        return "short"
    if (raw_exit > 0 and position < 0) or (raw_exit < 0 and position > 0):
        return "flat"
    return None
