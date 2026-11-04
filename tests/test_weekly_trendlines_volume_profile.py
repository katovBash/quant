"""Check causal mapping and basic proxy behavior on cached, fixed candles."""

import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiments/double-indicator/weekly-trendlines-volume-profile/levels.py"
spec = importlib.util.spec_from_file_location("weekly_levels", PATH)
levels = importlib.util.module_from_spec(spec)
spec.loader.exec_module(levels)


class WeeklyLevelsTest(unittest.TestCase):
    def test_current_week_excluded_from_lower_timeframe(self):
        weeks = [{"ts": "2026-10-19 00:00:00"}, {"ts": "2026-10-26 00:00:00"}]
        values = [(101.0, 91.0), (200.0, 20.0)]
        bars = [{"ts": "2026-10-23 12:00:00"}, {"ts": "2026-10-29 12:00:00"}]
        self.assertTrue(math.isnan(levels.map_prior_week(bars, weeks, values)[0][0]))
        self.assertEqual(levels.map_prior_week(bars, weeks, values)[1], values[0])

    def test_volume_profile_uses_volume_and_value_area(self):
        bars = [
            {"low": 10.0, "high": 11.0, "volume": 1000},
            {"low": 20.0, "high": 21.0, "volume": 1},
        ]
        val, vah, poc = levels._profile(bars)
        self.assertTrue(10 <= val <= poc <= vah < 20)

    def test_rejection_is_single_first_touch(self):
        bars = [{"low": 99.8, "high": 101, "close": 100.5}] * 35
        signals = levels.rejection_signals(bars, [(math.nan, 100)] * 35, [1.0] * 35)
        self.assertEqual([i for i, signal in enumerate(signals) if signal], [33])


if __name__ == "__main__":
    unittest.main()
