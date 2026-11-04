import unittest

from src.ema.core.research_ema_heikin_ashi import heikin_ashi


class HeikinAshiTests(unittest.TestCase):
    def test_ha_close_and_recursive_open(self):
        bars = [
            {"ts": "2024-01-01", "open": 10.0, "high": 16.0, "low": 8.0, "close": 14.0, "volume": 10},
            {"ts": "2024-01-02", "open": 14.0, "high": 20.0, "low": 12.0, "close": 18.0, "volume": 10},
        ]
        result = heikin_ashi(bars)
        self.assertEqual(result[0]["close"], 12.0)
        self.assertEqual(result[0]["open"], 12.0)
        self.assertEqual(result[1]["close"], 16.0)
        self.assertEqual(result[1]["open"], 12.0)
        self.assertEqual(bars[1]["open"], 14.0)  # market fill differs from HA open


if __name__ == "__main__":
    unittest.main()
