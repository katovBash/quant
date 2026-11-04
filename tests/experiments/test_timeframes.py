"""Intraday research bars must come from earlier, correctly grouped minute bars."""

import json
import tempfile
import unittest
from pathlib import Path

from src.research.timeframes import aggregate_minutes, load_research_bars, source_path


class IntradayFramesTests(unittest.TestCase):
    def setUp(self):
        self.minute = [
            {"ts": "2026-01-05 10:00:00", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 3},
            {"ts": "2026-01-05 10:14:00", "open": 101, "high": 104, "low": 100, "close": 103, "volume": 4},
            {"ts": "2026-01-05 10:15:00", "open": 103, "high": 105, "low": 102, "close": 104, "volume": 5},
            {"ts": "2026-01-05 10:29:00", "open": 104, "high": 106, "low": 101, "close": 105, "volume": 6},
            {"ts": "2026-01-05 10:30:00", "open": 105, "high": 107, "low": 104, "close": 106, "volume": 7},
        ]

    def test_15_and_30_minute_ohlcv(self):
        m15 = aggregate_minutes(self.minute, 15)
        m30 = aggregate_minutes(self.minute, 30)
        self.assertEqual([(bar["open"], bar["high"], bar["low"], bar["close"], bar["volume"])
                          for bar in m15], [(100, 104, 99, 103, 7), (103, 106, 101, 105, 11),
                                            (105, 107, 104, 106, 7)])
        self.assertEqual([(bar["open"], bar["high"], bar["low"], bar["close"], bar["volume"])
                          for bar in m30], [(100, 106, 99, 105, 18), (105, 107, 104, 106, 7)])

    def test_minute_cache_is_required_not_hourly_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "PLZL_60_2024-01-01_2026-10-30.json").write_text("[]")
            with self.assertRaises(FileNotFoundError):
                load_research_bars(cache, "PLZL", "15M")
            source_path(cache, "PLZL", "15M").write_text(json.dumps(self.minute))
            self.assertEqual(len(load_research_bars(cache, "PLZL", "15M")), 3)

    def test_unsorted_minutes_rejected(self):
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            aggregate_minutes(self.minute[::-1], 15)


if __name__ == "__main__":
    unittest.main()
