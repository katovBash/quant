"""The accelerated exhaustive sweep must match the established Python backtest."""

import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from src.ema.core.scan_ema import backtest

ROOT = Path(__file__).resolve().parents[2]


class GridParityTests(unittest.TestCase):
    def test_trade_counts_and_returns_match_python_for_each_mode_and_period(self):
        prices = [100] * 20 + [110] * 20 + [90] * 20 + [115] * 20
        bars = [{"ts": str(date(2020, 1, 1) + timedelta(days=i)) + " 00:00:00",
                 "open": p, "close": p, "high": p, "low": p, "volume": 1000}
                for i, p in enumerate(prices)]
        with tempfile.TemporaryDirectory() as directory:
            exe = Path(directory) / "kernel"
            subprocess.run(["g++", "-std=c++17", "-O2",
                            str(ROOT / "experiments/ema-grid-search/kernel.cpp"),
                            "-o", str(exe)], check=True)
            data = "".join(f'{b["ts"]},{b["open"]},{b["close"]}\n' for b in bars)
            output = subprocess.run([str(exe), "2020-01-01", "2020-02-15", "5", "0", "0.1", "5"],
                                    input=data, text=True, capture_output=True, check=True).stdout
            rows = [line.split(",") for line in output.splitlines()]
            for row in rows:
                fast, slow, mode = map(int, row[:3])
                direction = ("long", "short", "long_short")[mode]
                actual = backtest(bars, fast, slow, "2020-01-01", 5, 0, 0.1, direction)
                later = backtest(bars, fast, slow, "2020-02-15", 5, 0, 0.1, direction)
                self.assertEqual(int(row[4]), actual["trades"])
                self.assertEqual(int(row[5]), actual["wins"])
                self.assertAlmostEqual(float(row[6]), actual["net"], places=3)
                self.assertEqual(int(row[10]), later["trades"])
                self.assertAlmostEqual(float(row[12]), later["net"], places=3)


if __name__ == "__main__":
    unittest.main()
