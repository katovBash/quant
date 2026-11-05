"""New rolling-extrema implementation must preserve the frozen Turtle signals."""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TurtlePeriodGridTests(unittest.TestCase):
    def test_matches_original_and_excludes_future_bar(self):
        original = load("three_trader_signals_ref", ROOT / "experiments/three-trader-rules/signals.py")
        grid = load("turtle_grid_signals", ROOT / "experiments/turtle/period-grid/signals.py")
        bars = json.loads((ROOT / "data/candles/moex_scan/SBER_60_2024-01-01_2026-10-30.json").read_text())[:400]
        extrema = grid.prior_extrema(bars, {5, 10, 20, 55, 70})
        for entry, exit_length in ((20, 10), (55, 20), (70, 5)):
            self.assertEqual(grid.turtle_from_extrema(bars, entry, exit_length, extrema),
                             original.turtle(bars, entry, exit_length))
        changed = [dict(bar) for bar in bars]
        changed[-1]["high"] *= 100
        changed[-1]["low"] /= 100
        prior = grid.prior_extrema(changed, {20, 10})
        self.assertEqual(extrema[20][0][-1], prior[20][0][-1])
        self.assertEqual(extrema[10][1][-1], prior[10][1][-1])


if __name__ == "__main__":
    unittest.main()
