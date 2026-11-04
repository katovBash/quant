"""Guard the causal SMA/ATR filter experiment and its frozen baseline."""

import importlib.util
import unittest
from pathlib import Path

from src.research.indicator_library import sma
from src.research.standalone_grid import atr, load_bars


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "experiments/double-indicator/sma-cross-sideways-filters-smlt-1h/run.py"
SPEC = importlib.util.spec_from_file_location("sma_sideways_run", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
STRATEGY_FILE = ROOT / "strategies/sma-cross-10-59-atr025-long-short-1h/strategy.py"
STRATEGY_SPEC = importlib.util.spec_from_file_location("smlt_sma_zone_strategy", STRATEGY_FILE)
STRATEGY = importlib.util.module_from_spec(STRATEGY_SPEC)
STRATEGY_SPEC.loader.exec_module(STRATEGY)


class SidewaysFilterExperimentTests(unittest.TestCase):
    def test_frozen_strategy_matches_experiment_signals(self):
        bars = load_bars("SMLT", "1H")
        close = [bar["close"] for bar in bars]
        expected = MODULE.hysteresis_signals(sma(close, 10), sma(close, 59),
                                             atr(bars, 14), 0.25)
        self.assertEqual(STRATEGY.signal_series(bars), expected)

    def test_future_candle_cannot_change_prior_signals(self):
        bars = load_bars("SMLT", "1H")[:100]

        def signals(source):
            close = [bar["close"] for bar in source]
            return MODULE.hysteresis_signals(sma(close, 12), sma(close, 60),
                                             atr(source, 14), 0.25)

        original = signals(bars)
        future = dict(bars[-1], ts="2026-11-01 00:00:00", open=9999.0,
                      high=9999.0, low=9999.0, close=9999.0)
        self.assertEqual(original, signals(bars + [future])[:-1])

    def test_baseline_reproduces_frozen_sma_result(self):
        baseline = next(row for row in MODULE.run() if row["variant"] == "baseline"
                        and row["period"] == "all_seen_history")
        self.assertEqual((baseline["return_pct"], baseline["closed_trades"]),
                         (118.68, 267))


if __name__ == "__main__":
    unittest.main()
