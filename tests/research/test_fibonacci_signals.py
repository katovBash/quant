"""The Fibonacci research rule must not revise earlier signals using future bars."""

import math
import unittest

from src.research.fibonacci_signals import retracement_signals


class FibonacciCausalityTests(unittest.TestCase):
    def test_appending_future_bars_does_not_change_past_signals(self):
        bars = []
        for i in range(80):
            center = 100 + 7 * math.sin(i / 3) + i * 0.05
            bars.append({"open": center - 0.2, "high": center + 1,
                         "low": center - 1, "close": center + 0.2})
        full_entries, full_exits = retracement_signals(bars, 3, 0.618, 0.25)
        for length in (30, 45, 60):
            entries, exits = retracement_signals(bars[:length], 3, 0.618, 0.25)
            self.assertEqual(entries, full_entries[:length])
            self.assertEqual(exits, full_exits[:length])


if __name__ == "__main__":
    unittest.main()
