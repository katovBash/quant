import unittest

from src.ema.core.adx_ema import backtest
from src.ema.core.research_ema_combinations import crosses, double_patterns, gates, simulate


class PatternResearchTests(unittest.TestCase):
    def test_simulator_matches_existing_baseline(self):
        closes = [100 + 7 * ((i // 12) % 2) + i * 0.02 for i in range(110)]
        bars = [{"ts": f"2024-01-{1 + i // 24:02d} {i % 24:02d}:00:00",
                 "open": p, "high": p + 1, "low": p - 1, "close": p, "volume": 1000}
                for i, p in enumerate(closes)]
        actual = simulate(bars, crosses(bars), [True] * len(bars), [True] * len(bars), 0.01, "2024-01-01")
        expected = backtest(bars, [], 0, "2024-01-01", 0.01)
        for key in ("return_pct", "max_drawdown_pct", "closed_trades", "winning_trades"):
            self.assertEqual(actual[key], expected[key])

    def test_future_bars_do_not_change_prior_pattern_gates(self):
        bars = [{"open": 100.0 + i * 0.1, "high": 101.0 + i * 0.1,
                 "low": 99.0 + i * 0.1, "close": 100.5 + i * 0.1,
                 "volume": 1000.0} for i in range(50)]
        original = gates(bars)
        changed = gates(bars + [{"open": 50.0, "high": 150.0, "low": 20.0,
                                 "close": 140.0, "volume": 50000.0}])
        for name in original:
            self.assertEqual(original[name][0], changed[name][0][:50])
            self.assertEqual(original[name][1], changed[name][1][:50])

    def test_double_bottom_waits_for_confirmed_second_low_and_neckline(self):
        bars = [{"open": 108, "high": 111, "low": 105, "close": 108, "volume": 100}
                for _ in range(45)]
        bars[10]["low"] = 100
        bars[18]["high"] = 115
        bars[25]["low"] = 101
        bars[29].update(high=117, close=116)
        bullish, bearish = double_patterns(bars)
        self.assertFalse(any(bullish[:29]))
        self.assertTrue(bullish[29])
        self.assertFalse(any(bearish))


if __name__ == "__main__":
    unittest.main()
