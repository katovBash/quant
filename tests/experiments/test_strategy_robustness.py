import unittest

from src.research.standalone_grid import ema_level_signals
from src.research.strategy_robustness import add_months, strategy_signals, underwater
from tests.experiments.test_standalone_grid import bars
from datetime import date


class StrategyRobustnessTests(unittest.TestCase):
    def test_ema_width_from_strategy_id_matches_frozen_rule(self):
        sample = bars(100)
        for strategy_id, period, width in (
            ("ema-level-25-atr05-long-short-1d", 25, 0.5),
            ("ema-level-45-atr025-long-short-1h", 45, 0.25),
        ):
            self.assertEqual(strategy_signals(strategy_id, {}, sample),
                             ema_level_signals(sample, period, width))

    def test_underwater_includes_unrecovered_stretch(self):
        curve = [{"date": "2024-01-01", "equity": 1_010_000},
                 {"date": "2024-01-02", "equity": 990_000},
                 {"date": "2024-01-11", "equity": 995_000}]
        self.assertEqual(underwater(curve),
                         {"calendar_days": 9, "start": "2024-01-02",
                          "end": "2024-01-11", "recovered": False})

    def test_month_step_crosses_year(self):
        self.assertEqual(add_months(date(2024, 12, 1), 2), date(2025, 2, 1))


if __name__ == "__main__":
    unittest.main()
