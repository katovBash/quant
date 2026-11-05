"""Run one preregistered ZigZag use case through the shared universe runner."""

from __future__ import annotations

from pathlib import Path

from src.research.trader_method_run import run
from src.research.zigzag_signals import (
    compression_signals, retest_signals, trendline_signals,
)


def run_experiment(experiment: Path, *, smoke: bool = False):
    case = experiment.name

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
        raise ValueError(f"unknown ZigZag case: {case}")

    return run(experiment, smoke=smoke, signal_factory=signal_factory)
