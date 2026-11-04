"""Causality and fill-timing checks for public trader-rule adaptations."""

import importlib.util
import unittest
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate

PATH = Path(__file__).resolve().parents[1] / "experiments/three-trader-rules/signals.py"
spec = importlib.util.spec_from_file_location("three_trader_signals", PATH)
signals_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signals_module)


def sample_bars(count=70):
    bars = []
    for i in range(count):
        close = 100 + (i % 5) * 0.1
        bars.append({"ts": "2024-01-01 00:00:00", "open": close, "high": close + 1,
                     "low": close - 1, "close": close, "volume": 1000})
    return bars


class PublicRulesTest(unittest.TestCase):
    def test_turtle_excludes_current_and_future_bar(self):
        bars = sample_bars()
        bars[30]["close"] = 110
        initial, _ = signals_module.turtle(bars, 20, 10)
        self.assertEqual(initial[30], 1)
        bars[31]["high"] = 1000
        changed, _ = signals_module.turtle(bars, 20, 10)
        self.assertEqual(changed[:31], initial[:31])

    def test_simulator_fills_after_signal_close(self):
        bars = sample_bars(36)
        for i in range(36):
            bars[i]["ts"] = f"2024-01-{i // 4 + 1:02d} 00:00:00"
        bars[33]["close"] = 50
        bars[34]["open"] = 100
        bars[34]["close"] = 100
        bars[35]["close"] = 110
        entries = [0] * len(bars)
        entries[33] = 1
        curve = []
        simulate(bars, entries, [True] * len(bars), [True] * len(bars), 0,
                 "2024-01-01", fee_bps=0, equity_curve=curve)
        self.assertEqual(curve[0]["position"], 0)
        self.assertEqual(curve[1]["position"], 5000)
        self.assertEqual(curve[2]["equity"], 1050000)


if __name__ == "__main__":
    unittest.main()
