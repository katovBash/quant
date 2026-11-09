"""Daily moving-average confirmation for long entries of fixed Dual ZigZag."""

from __future__ import annotations

import importlib.util
import json
import sys
from bisect import bisect_left
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run

PARENT = ROOT / "experiments/dual-zigzag/price-oscillator-swings/run.py"
spec = importlib.util.spec_from_file_location("frozen_dual_zigzag", PARENT)
if spec is None or spec.loader is None:
    raise RuntimeError("parent experiment unavailable")
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
FIXED_VARIANT = "dual_5_2_14_trend-opp"


def completed_daily_from_intraday(bars: list[dict]) -> list[dict]:
    """Form daily closes from the same completed signal-bar source."""
    daily = []
    for bar in bars:
        day = bar["ts"][:10]
        if not daily or daily[-1]["ts"][:10] != day:
            daily.append({"ts": day, "close": bar["close"]})
        else:
            daily[-1]["close"] = bar["close"]
    return daily


def daily_long_allowed(bars: list[dict], daily: list[dict], length: int):
    """At each intraday close, use only prior completed daily candles."""
    dates = [bar["ts"][:10] for bar in daily]
    closes = [bar["close"] for bar in daily]
    prefix = [0.0]
    for close in closes:
        prefix.append(prefix[-1] + close)
    allowed = [False] * len(bars)
    previous_day, index, condition = None, 0, False
    for i, bar in enumerate(bars):
        day = bar["ts"][:10]
        if day != previous_day:
            index = bisect_left(dates, day)
            previous_day = day
            condition = (index >= length and
                         closes[index - 1] > (prefix[index] - prefix[index - length]) / length)
        allowed[i] = condition
    return allowed


def factory(symbol: str, timeframe: str, daily_override: list[dict] | None = None):
    cached = {}

    def signals(variant: str, bars: list[dict]):
        if "parent" not in cached:
            cached["parent"] = parent.factory(symbol, timeframe)(FIXED_VARIANT, bars)
        original, _ = cached["parent"]
        if variant == "parent":
            return original[:], original[:]
        if variant == "short_only":
            return [side if side < 0 else 0 for side in original], original[:]
        length = int(variant.removeprefix("sma_"))
        if "daily" not in cached:
            cached["daily"] = (daily_override if daily_override is not None else
                               completed_daily_from_intraday(bars))
        if length not in cached:
            cached[length] = daily_long_allowed(bars, cached["daily"], length)
        entries = [side if side < 0 or (side > 0 and cached[length][i]) else 0
                   for i, side in enumerate(original)]
        return entries, original[:]

    return signals


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    protocol = json.loads((experiment / "protocol.json").read_text())
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(experiment, smoke="--smoke" in sys.argv, context_factory=factory)
