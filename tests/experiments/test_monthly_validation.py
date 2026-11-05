"""Monthly reports must not silently accept missing months or wrong percentages."""

import unittest

from src.research.monthly_validation import validate_monthly_rows


def month(start, end, initial, final, return_pct, pnl, trades=1, wins=1):
    return {"symbol": "AAA", "timeframe": "1H", "variant": "rule",
            "start": start, "end_exclusive": end,
            "starting_equity_rub": str(initial), "ending_equity_rub": str(final),
            "return_pct": str(return_pct), "pnl_rub": str(pnl),
            "closed_trades": str(trades), "winning_trades": str(wins)}


class MonthlyValidationTests(unittest.TestCase):
    def test_gap_is_visible_without_corrupting_valid_months(self):
        rows = [month("2026-01-01", "2026-02-01", 100, 110, 10, 10),
                month("2026-03-01", "2026-04-01", 110, 121, 10, 11)]
        result = validate_monthly_rows(rows)
        self.assertTrue(result["ok"])
        self.assertFalse(result["continuous"])
        self.assertEqual(result["gap_pairs"], 1)
        self.assertEqual(result["missing_months_inside_history"], 1)
        self.assertEqual(result["affected_symbol_timeframes"], 1)
        self.assertEqual(result["unique_missing_symbol_months"], 1)
        self.assertEqual(result["gap_examples"][0]["first_missing"], ["2026-02"])

    def test_wrong_arithmetic_duplicate_and_invalid_trades_fail(self):
        correct = month("2026-01-01", "2026-02-01", 100, 110, 10, 10)
        wrong = month("2026-01-01", "2026-02-01", 100, 110, 8, 9, 0, 1)
        wrong_date = month("2026-02-01", "2026-02-28", 110, 121, 10, 11)
        result = validate_monthly_rows([correct, wrong, wrong_date])
        self.assertFalse(result["ok"])
        self.assertEqual(result["duplicate_month_rows"], 1)
        self.assertEqual(result["return_mismatch_rows"], 1)
        self.assertEqual(result["pnl_mismatch_rows"], 1)
        self.assertEqual(result["invalid_trade_rows"], 1)
        self.assertEqual(result["invalid_calendar_rows"], 1)


if __name__ == "__main__":
    unittest.main()
