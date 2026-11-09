"""Run one preregistered ZigZag use case through the shared universe runner."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from src.research.trader_method_run import run
from src.research.zigzag_signals import (
    compression_signals, parallel_second_touch_signals, retest_signals, trendline_signals,
    third_touch_signals,
)
from src.research.timeframes import load_research_bars

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/candles/moex_scan"


def run_experiment(experiment: Path, *, smoke: bool = False):
    case = experiment.name

    @lru_cache(maxsize=512)
    def higher_bars(symbol, source):
        return load_research_bars(CACHE, symbol, source)

    def context_factory(symbol, timeframe):
        def signal_factory(variant, bars):
            return third_touch_variant(variant, bars, symbol)
        return signal_factory

    def third_touch_variant(variant, bars, symbol):
        parts = variant.split("_")
        if case == "parallel-channel-second-touch":
            kind, preset, source, exit_code = parts
            wing, deviation, zone, age = {"a": (3, 2.0, 0.5, 50),
                                          "b": (5, 4.0, 1.0, 100)}[preset]
            if source not in ("c", "d", "w") or exit_code not in ("line", "t3", "t5"):
                raise ValueError("unknown parallel channel variant")
            line_bars = None if source == "c" else higher_bars(symbol, "1D" if source == "d" else "1W")
            if kind == "pc":
                return parallel_second_touch_signals(
                    bars, wing, deviation, zone, age, line_bars=line_bars,
                    exit_mode={"line": "opposite_line", "t3": "tp_3", "t5": "tp_5"}[exit_code])
            if kind == "tc" and exit_code != "line":
                return third_touch_signals(bars, wing, deviation, zone, age, "bounce",
                                           line_bars=line_bars, exit_mode="tp_" + exit_code[1:])
            raise ValueError("unknown parallel channel control")
        if case == "third-touch-exits":
            presets = {"a": (3, 2.0, 0.5, 50), "b": (5, 4.0, 1.0, 100)}
            wing, deviation, zone, age = presets[parts[1]]
            source, code, exit_code = parts[2:5]
        else:
            wing, deviation, zone, age = int(parts[1]), float(parts[2]), float(parts[3]), int(parts[4])
            source, code = parts[5], parts[6]
            exit_code = "op"
        style = "bounce" if code == "b" else "breakout" if code == "x" else None
        if source not in ("c", "d", "w"):
            raise ValueError(f"unknown line source: {source}")
        line_bars = None if source == "c" else higher_bars(symbol, "1D" if source == "d" else "1W")
        exits = {"op": "opposite_signal", "line": "opposite_line",
                 "t3": "tp_3", "t5": "tp_5", "t8": "tp_8"}
        if exit_code not in exits:
            raise ValueError(f"unknown exit mode: {exit_code}")
        return third_touch_signals(bars, wing, deviation, zone, age, style,
                                   line_bars=line_bars, exit_mode=exits[exit_code])

    def signal_factory(variant, bars):
        parts = variant.split("_")
        wing, deviation = int(parts[1]), float(parts[2])
        extra = float(parts[3])
        if case == "confirmed-level-retest":
            return retest_signals(bars, wing, deviation, extra)
        if case == "confirmed-trendline-breakout":
            return trendline_signals(bars, wing, deviation, int(extra))
        if case == "confirmed-triangle-breakout":
            return compression_signals(bars, wing, deviation, extra)
        if case in ("third-touch-line", "third-touch-exits", "parallel-channel-second-touch"):
            raise ValueError("third-touch requires symbol/timeframe context")
        raise ValueError(f"unknown ZigZag case: {case}")

    return run(experiment, smoke=smoke,
               context_factory=context_factory if case in ("third-touch-line", "third-touch-exits", "parallel-channel-second-touch") else None,
               signal_factory=signal_factory if case not in ("third-touch-line", "third-touch-exits", "parallel-channel-second-touch") else None)
