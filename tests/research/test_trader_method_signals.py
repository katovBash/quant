"""Research signals must not change when a later candle arrives."""

import unittest

from scripts.seed_trader_methods import METHODS
from src.research.trader_method_signals import signals


class TraderMethodSignalTests(unittest.TestCase):
    def test_all_methods_are_past_only(self):
        bars = []
        for i in range(130):
            price = 100 + i * 0.13 + ((i % 11) - 5) * 0.7
            bars.append({"ts": f"2024-01-{i // 24 + 1:02d}T{i % 24:02d}:00:00",
                         "open": price - 0.2, "high": price + 0.9,
                         "low": price - 1.1, "close": price,
                         "volume": 1000 + (i % 7) * 100})
        for _, method, values, _, _, _, _ in METHODS:
            with self.subTest(method=method):
                full_entries, full_exits = signals(method, bars, values[0])
                short_entries, short_exits = signals(method, bars[:-1], values[0])
                self.assertEqual(full_entries[:-1], short_entries)
                self.assertEqual(full_exits[:-1], short_exits)


if __name__ == "__main__":
    unittest.main()
