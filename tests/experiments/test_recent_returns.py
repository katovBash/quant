"""Rolling returns use consecutive full months and continuous equity."""

import unittest

from src.research.recent_returns import trailing_period


class RecentReturnsTests(unittest.TestCase):
    def test_compounds_continuous_equity_instead_of_adding_monthly_percentages(self):
        months = [
            {"start": "2026-07-01", "starting_equity_rub": "100", "ending_equity_rub": "110"},
            {"start": "2026-08-01", "starting_equity_rub": "110", "ending_equity_rub": "121"},
            {"start": "2026-09-01", "starting_equity_rub": "121", "ending_equity_rub": "108.9"},
        ]
        self.assertEqual(trailing_period(months, 3), {
            "return_pct": 8.9, "pnl_rub": 8.9,
            "from_month": "2026-07", "through_month": "2026-09"})
        self.assertEqual(trailing_period(months, 1)["return_pct"], -10.0)

    def test_missing_month_does_not_create_a_false_period(self):
        months = [
            {"start": "2026-07-01", "starting_equity_rub": "100", "ending_equity_rub": "110"},
            {"start": "2026-09-01", "starting_equity_rub": "110", "ending_equity_rub": "121"},
        ]
        self.assertIsNone(trailing_period(months, 3))
        self.assertIsNone(trailing_period(months, 2))


if __name__ == "__main__":
    unittest.main()
