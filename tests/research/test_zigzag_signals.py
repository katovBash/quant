"""A future candle cannot change already emitted ZigZag breakout events."""

import unittest

from src.research.zigzag_signals import (
    breakout_signals, compression_signals, confirmed_pivots, retest_signals,
    trendline_signals,
)


class ZigZagSignalTests(unittest.TestCase):
    def setUp(self):
        self.bars = []
        for i in range(70):
            center = 100 + (i % 9 - 4) * 2 + i * 0.03
            self.bars.append({"open": center - 0.3, "high": center + 1,
                              "low": center - 1, "close": center})

    def test_pivot_is_available_only_after_right_wing(self):
        for confirmed_at, pivot_at, _, _ in confirmed_pivots(self.bars, 3, 2):
            self.assertGreaterEqual(confirmed_at - pivot_at, 3)

    def test_prefix_signals_do_not_repaint(self):
        factories = (
            lambda bars, wing, deviation: breakout_signals(bars, wing, deviation),
            lambda bars, wing, deviation: retest_signals(bars, wing, deviation, 0.5),
            lambda bars, wing, deviation: trendline_signals(bars, wing, deviation, 50),
            lambda bars, wing, deviation: compression_signals(bars, wing, deviation, 25),
        )
        for factory in factories:
            for wing in (2, 3, 5):
                for deviation in (2, 4, 6):
                    full = factory(self.bars, wing, deviation)
                    for cutoff in (25, 40, 60):
                        prefix = factory(self.bars[:cutoff], wing, deviation)
                        self.assertEqual(tuple(part[:cutoff] for part in full), prefix)


if __name__ == "__main__":
    unittest.main()
