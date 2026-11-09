"""Frozen control selected in the EMA support/resistance comparison.

This rule is identical to the already fixed Dual ZigZag + daily SMA20 strategy.
It does not add an EMA entry condition.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

STRATEGY_ID = "dual-zigzag-ema-study-sma20-control-4h"
TIMEFRAME = "4H"
VARIANT = "zz_sma20"
PAPER_SYMBOLS = ["VKCO", "NLMK", "WUSH", "SFIN", "UGLD", "PLZL", "ALRS", "SELG"]
USES_POSITION = True

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "strategies/dual-zigzag-daily-sma20-4h/strategy.py"
spec = importlib.util.spec_from_file_location("existing_dual_zigzag_sma20_control", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("existing fixed control unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def events(completed_4h_bars: list[dict]) -> tuple[int, int]:
    return module.events(completed_4h_bars)


def signal(completed_4h_bars: list[dict], *, position: int = 0) -> str | None:
    return module.signal(completed_4h_bars, position=position)
