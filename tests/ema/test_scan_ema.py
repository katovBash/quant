import unittest
from datetime import date, timedelta

from src.ema.core.scan_ema import backtest, scan_one


def make_bars(prices):
    return [{"ts": str(date(2020, 1, 1) + timedelta(days=i)) + " 00:00:00",
             "open": p, "high": p, "low": p, "close": p, "volume": 1000}
            for i, p in enumerate(prices)]


class ScanTests(unittest.TestCase):
    def test_three_directions_are_distinct_and_reversal_closes_both_sides(self):
        bars = make_bars([100] * 20 + [110] * 20 + [90] * 20 + [110] * 20)
        results = {mode: backtest(bars, 2, 5, "2020-01-01", 5, 0, 0.1, mode)
                   for mode in ("long", "short", "long_short")}
        self.assertEqual(results["long"]["trades"], 1)
        self.assertEqual(results["short"]["trades"], 1)
        self.assertEqual(results["long_short"]["trades"], 2)

    def test_signal_is_filled_at_next_open(self):
        bars = make_bars([100] * 20 + [110] * 20 + [90] * 20)
        original = backtest(bars, 2, 5, "2020-01-01", 0, 0, 0, "long")
        # Up-cross occurs on the first 110 close; its order fills on the next bar.
        bars[21]["open"] = 130
        changed = backtest(bars, 2, 5, "2020-01-01", 0, 0, 0, "long")
        self.assertLess(changed["net"], original["net"])

    def test_short_history_is_marked_unknown(self):
        bars = make_bars([100] * 20)
        rows = scan_one("TEST", "1D", bars, ((12, 33),), "2020-01-01",
                        "2020-01-10", 5, 0, 0.01)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["status"] == "insufficient_history" for r in rows))


if __name__ == "__main__":
    unittest.main()
