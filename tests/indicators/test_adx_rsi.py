import math
import unittest

from src.ema.core.adx_ema import adx
from src.ema.core.compare_ema_filters import rsi


class IndicatorTests(unittest.TestCase):
    def test_adx_strong_unidirectional_trend_and_warmup(self):
        bars = [
            {"high": 101.0 + i, "low": 99.0 + i, "close": 100.0 + i}
            for i in range(60)
        ]
        values = adx(bars, length=14)
        self.assertTrue(all(math.isnan(value) for value in values[:26]))
        self.assertAlmostEqual(values[-1], 100.0)

    def test_adx_and_rsi_do_not_look_into_future_bars(self):
        bars = [
            {"high": 102.0 + i, "low": 98.0 + i, "close": 100.0 + i}
            for i in range(45)
        ]
        extra = {"high": 400.0, "low": 1.0, "close": 300.0}
        before_adx = adx(bars)
        after_adx = adx(bars + [extra])
        before_rsi = rsi(bars)
        after_rsi = rsi(bars + [extra])
        for before, after in ((before_adx, after_adx), (before_rsi, after_rsi)):
            for old, new in zip(before, after):
                if math.isnan(old):
                    self.assertTrue(math.isnan(new))
                else:
                    self.assertAlmostEqual(old, new)

    def test_rsi_direction_and_flat_market(self):
        for change, expected in ((1.0, 100.0), (-1.0, 0.0), (0.0, 50.0)):
            bars = [{"close": 100.0 + i * change} for i in range(40)]
            self.assertAlmostEqual(rsi(bars, length=14)[-1], expected)


if __name__ == "__main__":
    unittest.main()
