"""Conservative checks must flag bad bars and uncertain intraday holes."""

import json
import tempfile
import unittest
from pathlib import Path

from src.research.data_quality import candle_quality
from src.research.timeframes import source_path


class DataQualityTests(unittest.TestCase):
    def test_intraday_hole_is_flagged_as_possible(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            path = source_path(cache, "TEST", "1H")
            path.write_text(json.dumps([
                {"ts": "2026-01-05 10:00:00", "open": 100, "high": 101, "low": 99, "close": 100},
                {"ts": "2026-01-05 12:00:00", "open": 100, "high": 101, "low": 99, "close": 100}]))
            actual = candle_quality(cache, "TEST", "1H")
            self.assertEqual(actual["status"], "possible_gaps")
            self.assertEqual(actual["possible_intraday_gaps"], 1)

    def test_bad_ohlc_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            path = source_path(cache, "TEST", "1D")
            path.write_text(json.dumps([
                {"ts": "2026-01-05 00:00:00", "open": 100, "high": 99, "low": 98, "close": 100}]))
            self.assertEqual(candle_quality(cache, "TEST", "1D")["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
