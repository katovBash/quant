import unittest

from src.research.trade_windows import trade_windows


class TradeWindowsTests(unittest.TestCase):
    def test_one_hundred_trade_windows_count_wins_and_pnl(self):
        trades = [{"entry_date": "2026-01-01", "exit_date": "2026-01-02",
                   "pnl_rub": 100 if index < 30 else -10}
                  for index in range(101)]
        rolling = trade_windows(trades)
        self.assertEqual(len(rolling), 2)
        self.assertEqual(rolling[0]["winning_trades"], 30)
        self.assertEqual(rolling[0]["win_rate_pct"], 30.0)
        self.assertEqual(rolling[0]["pnl_rub"], 2300)
        self.assertEqual(rolling[1]["winning_trades"], 29)
        self.assertEqual(len(trade_windows(trades, step=100)), 1)

    def test_incomplete_block_is_not_reported_as_hundred_trades(self):
        self.assertEqual(trade_windows([]), [])
        self.assertEqual(trade_windows([{"pnl_rub": 1}] * 99), [])


if __name__ == "__main__":
    unittest.main()
