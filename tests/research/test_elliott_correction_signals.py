import unittest

from src.research.elliott_correction_signals import correction_signals
from src.research.timeframes import aggregate_weeks


def bars(values):
    return [{"ts": f"2024-01-{i + 1:02d}", "open": value,
             "high": value + 0.1, "low": value - 0.1,
             "close": value, "volume": 1} for i, value in enumerate(values)]


class CorrectionSignalTests(unittest.TestCase):
    def test_wave2_enters_only_after_pivot_confirmation(self):
        series = bars([105, 103, 100, 102, 107, 112, 109, 107, 105,
                       108, 110, 111, 113, 115])
        entries, exits = correction_signals(series, "wave2", 2, 2, 25)
        self.assertEqual([i for i, value in enumerate(entries) if value], [11])
        for end in range(1, len(series) + 1):
            prefix = correction_signals(series[:end], "wave2", 2, 2, 25)
            self.assertEqual(prefix[0], entries[:end])
            self.assertEqual(prefix[1], exits[:end])

    def test_weekly_bar_uses_last_daily_close(self):
        series = bars([100, 102, 101, 104, 103, 105, 107])
        series[5]["ts"] = "2024-01-08"
        series[6]["ts"] = "2024-01-09"
        weeks = aggregate_weeks(series)
        self.assertEqual(len(weeks), 2)
        self.assertEqual(weeks[0]["open"], 100)
        self.assertEqual(weeks[0]["close"], 103)
        self.assertEqual(weeks[0]["ts"], "2024-01-05")
        self.assertEqual(weeks[1]["open"], 105)


if __name__ == "__main__":
    unittest.main()
