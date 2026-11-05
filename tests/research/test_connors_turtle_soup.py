"""Check causal false-breakout signals and fixed holding exit."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "experiments/single-indicator/connors-turtle-soup/run.py"
SPEC = importlib.util.spec_from_file_location("connors_turtle_soup_experiment", RUN)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TurtleSoupSignalsTests(unittest.TestCase):
    def test_reclaimed_prior_low_enters_after_confirmed_bar_and_exits_after_hold(self):
        bars = [{"low": 8, "high": 12, "close": 10}]
        bars += [{"low": 9, "high": 11, "close": 10} for _ in range(3)]
        bars += [{"low": 7, "high": 11, "close": 9}]
        bars += [{"low": 9, "high": 11, "close": 10} for _ in range(4)]
        levels = MODULE.prior_levels(bars, 4)
        signals, exits = MODULE.signals_for(bars, levels, separation=4, hold=3)
        self.assertEqual(signals[4], 1)
        self.assertEqual(exits[7], -1)
        self.assertEqual(sum(abs(value) for value in signals), 1)
        changed_future = [dict(item) for item in bars]
        changed_future[8]["low"] = 1
        self.assertEqual(MODULE.signals_for(changed_future,
                         MODULE.prior_levels(changed_future, 4), 4, 3)[0][4], 1)

    def test_recent_prior_low_fails_separation_gate(self):
        bars = [{"low": 9, "high": 11, "close": 10} for _ in range(4)]
        bars[3]["low"] = 8
        bars += [{"low": 7, "high": 11, "close": 9}]
        signals, _ = MODULE.signals_for(bars, MODULE.prior_levels(bars, 4), 3, 3)
        self.assertEqual(signals[4], 0)


if __name__ == "__main__":
    unittest.main()
