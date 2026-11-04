import math
import unittest

from src.ema.core.compare_ema_filters import filter_for, regression_channel, rsi, trendlines


class FilterTimingTests(unittest.TestCase):
    def test_trendline_uses_only_confirmed_pivots(self):
        highs = [1, 2, 3, 9, 3, 2, 1, 2, 4, 10, 4, 2, 1]
        bars = [{"high": high, "low": 0, "close": high / 2} for high in highs]
        values = trendlines(bars)
        self.assertTrue(math.isnan(values[11][0]))
        self.assertTrue(math.isfinite(values[12][0]))

    def test_rsi_direction_gate_is_neutral_for_flat_prices(self):
        bars = [{"close": 100.0}] * 40
        values = rsi(bars)
        gate = filter_for("rsi-filter", bars)
        self.assertEqual(values[-1], 50.0)
        self.assertFalse(gate(39, 1))
        self.assertFalse(gate(39, -1))

    def test_channel_rejects_crossed_lines(self):
        bars = [{"high": 100 + i, "low": 90 + i, "close": 95 + i} for i in range(40)]
        gate = filter_for("channel-zone-filter", bars)
        self.assertFalse(gate(39, 1))
        self.assertFalse(gate(39, -1))

    def test_regression_channel_uses_past_only_and_projects_slope(self):
        bars = [{"close": 10.0 + 2 * i} for i in range(8)]
        values = regression_channel(bars, 4)
        self.assertTrue(math.isnan(values[3][0]))
        self.assertAlmostEqual(values[4][0], 18.0)
        self.assertAlmostEqual(values[4][1], 18.0)
        bars[4]["close"] = 1000.0
        self.assertEqual(values[4], regression_channel(bars, 4)[4])


if __name__ == "__main__":
    unittest.main()
