import unittest

from src.research.hourly_scalping_signals import session_vwap, signals


class HourlyScalpingSignalsTests(unittest.TestCase):
    def test_session_reset_holding_exit_and_no_future_leak(self):
        bars = []
        for day in range(1, 7):
            for hour in range(10, 14):
                bars.append({"ts": f"2026-01-{day:02d} {hour:02d}:00:00",
                             "open": 10.0, "high": 10.2, "low": 9.8,
                             "close": 10.0, "volume": 1000})
        bars[18].update(open=10.0, high=10.0, low=7.8, close=8.0)
        vwap, counts = session_vwap(bars)
        self.assertEqual(counts[4], 1)
        self.assertAlmostEqual(vwap[4], 10.0)
        entries, exits = signals(bars, 0.5, 2)
        self.assertEqual(entries[18], 1)
        self.assertEqual(exits[20], -1)
        changed = [dict(item) for item in bars]
        changed[23].update(high=100, low=1, close=2)
        self.assertEqual(signals(changed, 0.5, 2)[0][:23], entries[:23])


if __name__ == "__main__":
    unittest.main()
