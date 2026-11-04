import math
import unittest
from datetime import date, timedelta

from src.research.monthly_efficiency import (calendar_year_windows,
                                             continuous_monthly_windows,
                                             efficiency_ratio, monthly_windows)


class MonthlyEfficiencyTests(unittest.TestCase):
    def test_efficiency_ratio_separates_straight_move_from_chop(self):
        straight = efficiency_ratio([1, 2, 3, 4, 5], 4)
        chop = efficiency_ratio([1, 2, 1, 2, 1], 4)
        self.assertTrue(math.isnan(straight[3]))
        self.assertEqual(straight[4], 1.0)
        self.assertEqual(chop[4], 0.0)

    def test_future_close_does_not_change_previous_filter_values(self):
        closes = [100, 102, 99, 103, 104, 102]
        before = efficiency_ratio(closes, 3)
        after = efficiency_ratio(closes + [500], 3)
        self.assertEqual(before[3:], after[3:len(before)])

    def test_full_calendar_month_excludes_partial_last_month(self):
        bars = []
        for month in (1, 2):
            for day in range(1, 29):
                bars.append({"ts": f"2024-{month:02d}-{day:02d} 10:00:00",
                             "open": 100, "high": 101, "low": 99, "close": 100})
        signals = [0] * len(bars)
        report = monthly_windows(bars, signals, [True] * len(bars), 0.01, 2024, "2024-02-01")
        self.assertEqual(report["count"], 1)
        self.assertEqual(report["all"][0]["start"], "2024-01-01")
        self.assertEqual(report["all"][0]["sample"], "train")
        self.assertEqual(report["nonpositive_count"], 1)

    def test_calendar_year_regime_is_ex_post_and_partial_year_is_marked(self):
        bars = []
        for offset in range(366):
            day = date(2024, 1, 1) + timedelta(days=offset)
            bars.append({"ts": day.isoformat() + " 10:00:00", "open": 100,
                         "high": 121, "low": 99, "close": 120})
        for offset in range(20):
            day = date(2025, 1, 1) + timedelta(days=offset)
            bars.append({"ts": day.isoformat() + " 10:00:00", "open": 100,
                         "high": 101, "low": 79, "close": 80})
        years = calendar_year_windows(bars, [0] * len(bars),
                                      [True] * len(bars), 0.01, 2024)
        self.assertEqual([(row["year"], row["partial"], row["ex_post_regime"])
                          for row in years],
                         [(2024, False, "growth"), (2025, True, "decline")])

    def test_continuous_months_use_previous_month_end_equity(self):
        bars = [{"ts": stamp + " 10:00:00", "open": 100, "high": 101,
                 "low": 99, "close": 100} for stamp in
                ("2024-01-31", "2024-02-28", "2024-03-01")]
        curve = [{"date": "2024-01-31", "equity": 1_020_000},
                 {"date": "2024-02-28", "equity": 1_010_000},
                 {"date": "2024-03-01", "equity": 1_030_000}]
        trades = [{"entry_date": "2024-02-01", "exit_date": "2024-02-28",
                   "pnl_rub": -10_000}]
        result = continuous_monthly_windows(bars, curve, trades, 2024, "2024-02-01")
        self.assertEqual(result["count"], 2)
        self.assertEqual([row["pnl_rub"] for row in result["all"]], [20_000, -10_000])
        self.assertEqual(result["all"][1]["starting_equity_rub"], 1_020_000)
        self.assertEqual(result["nonpositive_count"], 1)


if __name__ == "__main__":
    unittest.main()
