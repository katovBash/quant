import unittest

from src.research.elliott_signals import _setup, impulse_breakout_signals


def bars(values):
    return [{"high": price + 0.1, "low": price - 0.1, "close": price}
            for price in values]


class ElliottSignalTests(unittest.TestCase):
    def test_wave3_waits_for_confirmed_second_low_and_breakout(self):
        series = bars([105, 103, 100, 102, 107, 112, 109, 107, 105, 108, 110, 111, 113, 115])
        entries, _ = impulse_breakout_signals(series, "wave3", 2, 2)
        self.assertEqual([index for index, signal in enumerate(entries) if signal], [12])

    def test_wave5_has_nonoverlap_and_no_lookahead(self):
        series = bars([105, 103, 100, 103, 108, 112, 109, 107, 105,
                       109, 116, 120, 117, 114, 113, 115, 118, 121])
        entries, exits = impulse_breakout_signals(series, "wave5", 2, 2)
        self.assertEqual([index for index, signal in enumerate(entries) if signal], [17])
        for end in range(6, len(series) + 1):
            prefix_entries, prefix_exits = impulse_breakout_signals(series[:end], "wave5", 2, 2)
            self.assertEqual(prefix_entries, entries[:end])
            self.assertEqual(prefix_exits, exits[:end])
        overlapping = [("low", 100, 1, 3), ("high", 112, 4, 6),
                       ("low", 105, 7, 9), ("high", 120, 10, 12),
                       ("low", 110, 13, 15)]
        self.assertIsNone(_setup(overlapping, "wave5", "long"))


if __name__ == "__main__":
    unittest.main()
