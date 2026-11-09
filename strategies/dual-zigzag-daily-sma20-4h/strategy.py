"""Fixed 4H Dual ZigZag rule with prior-completed-day SMA20 long filter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

STRATEGY_ID = "dual-zigzag-daily-sma20-4h"
TIMEFRAME = "4H"
VARIANT = "sma_20"
PAPER_SYMBOLS = ["VKCO", "NLMK", "WUSH", "SFIN", "UGLD", "PLZL", "ALRS", "SELG"]
USES_POSITION = True

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "experiments/double-indicator/dual-zigzag-daily-trend/run.py"
spec = importlib.util.spec_from_file_location("dual_zigzag_daily_trend", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("frozen experiment unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def completed_daily_from_four_hour(bars: list[dict]) -> list[dict]:
    """Build daily closes; the current signal day's value is excluded by the rule."""
    return module.completed_daily_from_intraday(bars)


def events(completed_4h_bars: list[dict]) -> tuple[int, int]:
    if len(completed_4h_bars) < 60:
        return 0, 0
    daily = completed_daily_from_four_hour(completed_4h_bars)
    accepted, raw = module.factory("", TIMEFRAME, daily_override=daily)(
        VARIANT, completed_4h_bars)
    return accepted[-1], raw[-1]


def signal(completed_4h_bars: list[dict], *, position: int = 0) -> str | None:
    """Signal on a completed 4H bar; paper executes at the next available bar."""
    accepted, raw = events(completed_4h_bars)
    if accepted > 0:
        return "long"
    if accepted < 0:
        return "short"
    if raw > 0 and position < 0:
        return "flat"
    return None
