"""Volume-flow confirmation for the frozen Dual ZigZag + daily SMA20 rule."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run

PARENT = ROOT / "experiments/double-indicator/dual-zigzag-daily-trend/run.py"
spec = importlib.util.spec_from_file_location("frozen_sma20", PARENT)
if spec is None or spec.loader is None:
    raise RuntimeError("parent experiment unavailable")
parent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)


def obv_series(bars: list[dict]) -> list[float]:
    """Cumulative signed observed volume, using each completed bar's close."""
    values = [0.0] * len(bars)
    for i in range(1, len(bars)):
        volume = bars[i].get("volume")
        if volume is None or float(volume) < 0:
            raise ValueError("OBV requires nonnegative observed volume on every bar")
        sign = 1 if bars[i]["close"] > bars[i - 1]["close"] else -1 if bars[i]["close"] < bars[i - 1]["close"] else 0
        values[i] = values[i - 1] + sign * float(volume)
    return values


def obv_delta(values: list[float], length: int) -> list[float | None]:
    result = [None] * len(values)
    for i in range(length, len(values)):
        result[i] = values[i] - values[i - length]
    return result


def standalone_signals(delta: list[float | None]) -> list[int]:
    entries = [0] * len(delta)
    for i in range(1, len(delta)):
        before, now = delta[i - 1], delta[i]
        if before is None or now is None:
            continue
        if before <= 0 < now:
            entries[i] = 1
        elif before >= 0 > now:
            entries[i] = -1
    return entries


def factory(symbol: str, timeframe: str):
    cached = {}

    def signals(variant: str, bars: list[dict]):
        if "parent" not in cached:
            cached["parent"] = parent.factory(symbol, timeframe)("sma_20", bars)
        parent_entries, parent_exits = cached["parent"]
        if variant == "parent":
            return parent_entries[:], parent_exits[:]
        family, length_text = variant.split("_")
        length = int(length_text)
        if "obv" not in cached:
            cached["obv"] = obv_series(bars)
        if length not in cached:
            cached[length] = obv_delta(cached["obv"], length)
        delta = cached[length]
        if family == "obv":
            entries = standalone_signals(delta)
            return entries, entries[:]
        entries = [0] * len(bars)
        for i, side in enumerate(parent_entries):
            if not side or delta[i] is None:
                continue
            if (side > 0 and delta[i] > 0) or (side < 0 and delta[i] < 0):
                entries[i] = side
        return entries, parent_exits[:]

    return signals


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    protocol = json.loads((experiment / "protocol.json").read_text())
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(experiment, smoke="--smoke" in sys.argv, context_factory=factory)
