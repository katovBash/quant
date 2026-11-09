"""Test ATR breakout-distance confirmation on a frozen Dual ZigZag rule."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run
from src.research.zigzag_signals import confirmed_pivots

PARENT = ROOT / "experiments/dual-zigzag/price-oscillator-swings/run.py"
spec = importlib.util.spec_from_file_location("frozen_dual_zigzag", PARENT)
if spec is None or spec.loader is None:
    raise RuntimeError("parent experiment unavailable")
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
FIXED_VARIANT = "dual_5_2_14_trend-opp"


def atr_before_signal(bars: list[dict], length: int = 14) -> list[float | None]:
    """Simple mean true range over the 14 bars completed before each decision."""
    ranges = [0.0] * len(bars)
    for i in range(1, len(bars)):
        bar = bars[i]
        previous_close = bars[i - 1]["close"]
        ranges[i] = max(bar["high"] - bar["low"],
                        abs(bar["high"] - previous_close),
                        abs(bar["low"] - previous_close))
    result = [None] * len(bars)
    total = 0.0
    for i in range(1, len(bars)):
        total += ranges[i - 1]
        if i > length:
            total -= ranges[i - length - 1]
        if i > length:
            result[i] = total / length
    return result


def level_before_signal(bars: list[dict]):
    levels = [None] * len(bars)
    last_high = last_low = None
    iterator = iter(confirmed_pivots(bars, 5, 2))
    upcoming = next(iterator, None)
    for i in range(len(bars)):
        levels[i] = (last_high, last_low)
        while upcoming and upcoming[0] == i:
            _, _, side, price = upcoming
            if side == "high":
                last_high = price
            else:
                last_low = price
            upcoming = next(iterator, None)
    return levels


def factory(symbol: str, timeframe: str):
    cached = {}

    def signals(variant: str, bars: list[dict]):
        if "parent" not in cached:
            cached["parent"] = parent.factory(symbol, timeframe)(FIXED_VARIANT, bars)
        original, _ = cached["parent"]
        multiplier = float(variant.removeprefix("atr_"))
        if multiplier == 0:
            return original[:], original[:]
        if "levels" not in cached:
            cached["levels"] = level_before_signal(bars)
            cached["atr"] = atr_before_signal(bars)
        entries = [0] * len(bars)
        for i, side in enumerate(original):
            if not side or cached["atr"][i] is None:
                continue
            high, low = cached["levels"][i]
            level = high if side > 0 else low
            if level is None:
                continue
            distance = (bars[i]["close"] - level) * side
            if distance >= multiplier * cached["atr"][i]:
                entries[i] = side
        return entries, entries[:]

    return signals


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    protocol = json.loads((experiment / "protocol.json").read_text())
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(experiment, smoke="--smoke" in sys.argv, context_factory=factory)
