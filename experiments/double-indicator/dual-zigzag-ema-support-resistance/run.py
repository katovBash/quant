"""Frozen Dual ZigZag entries tested against causal EMA support/resistance bounces."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from bisect import bisect_left
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.scan_ema import ema
from src.research.parameter_grid import variants_from_grid
from src.research.timeframes import load_research_bars
from src.research.trader_method_run import run


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


raw_module = _load_module("frozen_zigzag_price_rsi", ROOT /
                          "experiments/dual-zigzag/price-oscillator-swings/run.py")
sma_module = _load_module("frozen_zigzag_daily_sma", ROOT /
                          "experiments/double-indicator/dual-zigzag-daily-trend/run.py")
SOURCE = ROOT / "data/candles/moex_scan"
RAW_VARIANT = "dual_5_2_14_trend-opp"


def atr14(bars: list[dict]) -> list[float]:
    result = [math.nan] * len(bars)
    total = 0.0
    window = []
    for i, bar in enumerate(bars):
        previous = bars[i - 1]["close"] if i else bar["close"]
        tr = max(bar["high"] - bar["low"], abs(bar["high"] - previous),
                 abs(bar["low"] - previous))
        window.append(tr)
        total += tr
        if len(window) > 14:
            total -= window.pop(0)
        if len(window) == 14:
            result[i] = total / 14
    return result


def _week_key(stamp: str) -> int:
    week = date.fromisoformat(stamp[:10]).isocalendar()
    return week.year * 100 + week.week


def ema_contact_signals(bars: list[dict], higher_bars: list[dict] | None,
                        source: str, length: int, volatility: list[float]) -> list[int]:
    if source not in {"same", "day", "week"} or length not in {9, 20, 50, 100}:
        raise ValueError("undeclared EMA source or length")
    reference = bars if source == "same" else higher_bars
    if reference is None:
        raise ValueError("missing higher-timeframe candles")
    values = ema([bar["close"] for bar in reference], length)
    if source == "day":
        source_keys = [bar["ts"][:10] for bar in reference]
    elif source == "week":
        source_keys = [_week_key(bar["ts"]) for bar in reference]
    levels = [math.nan] * len(bars)
    slopes = [math.nan] * len(bars)
    for i, bar in enumerate(bars):
        if source == "same":
            index = i
        elif source == "day":
            index = bisect_left(source_keys, bar["ts"][:10]) - 1
        else:
            index = bisect_left(source_keys, _week_key(bar["ts"])) - 1
        if index < length or index >= len(values):
            continue
        levels[i] = values[index]
        slopes[i] = values[index] - values[index - 1]
    events = [0] * len(bars)
    for i in range(1, len(bars)):
        line, prior_line, movement, atr = levels[i], levels[i - 1], slopes[i], volatility[i]
        if not all(math.isfinite(v) for v in (line, prior_line, movement, atr)) or atr <= 0:
            continue
        current, previous = bars[i], bars[i - 1]
        if (previous["close"] >= prior_line and abs(current["low"] - line) <= 0.5 * atr
                and current["close"] > line and movement > 0):
            events[i] = 1
        elif (previous["close"] <= prior_line and abs(current["high"] - line) <= 0.5 * atr
              and current["close"] < line and movement < 0):
            events[i] = -1
    return events


def confirmed_entries(parent_entries: list[int], ema_events: list[int], window: str) -> list[int]:
    if window not in {"now", "recent5"}:
        raise ValueError("undeclared contact window")
    result = [0] * len(parent_entries)
    for i, side in enumerate(parent_entries):
        if not side:
            continue
        first = i if window == "now" else max(0, i - 5)
        if side in ema_events[first:i + 1]:
            result[i] = side
    return result


def factory(symbol: str, timeframe: str):
    cached = {}
    raw_factory = raw_module.factory(symbol, timeframe)
    sma_factory = sma_module.factory(symbol, timeframe)

    def signals(variant: str, bars: list[dict]):
        if "raw" not in cached:
            cached["raw"] = raw_factory(RAW_VARIANT, bars)
            cached["sma20"] = sma_factory("sma_20", bars)
        if variant == "zz_raw":
            entries, exits = cached["raw"]
            return entries[:], exits[:]
        if variant == "zz_sma20":
            entries, exits = cached["sma20"]
            return entries[:], exits[:]
        parts = variant.split("_")
        if parts[0] == "ema":
            _, source, length_text = parts
            base = None
        else:
            base, source, length_text, window = parts
        length = int(length_text)
        key = (source, length)
        if key not in cached:
            if "atr" not in cached:
                cached["atr"] = atr14(bars)
            if source in {"day", "week"} and source not in cached:
                cached[source] = load_research_bars(SOURCE, symbol,
                                                     "1D" if source == "day" else "1W")
            cached[key] = ema_contact_signals(
                bars, cached.get(source), source, length, cached["atr"])
        bounce = cached[key]
        if base is None:
            return bounce[:], bounce[:]
        base_entries = cached[base][0]
        raw_exits = cached["raw"][1]
        return confirmed_entries(base_entries, bounce, window), raw_exits[:]

    return signals


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    protocol = json.loads((experiment / "protocol.json").read_text())
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(experiment, smoke="--smoke" in sys.argv, context_factory=factory)
