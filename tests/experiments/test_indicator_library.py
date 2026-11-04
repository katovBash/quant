"""Check the preregistered 100-rule search before mass execution."""

import math
import unittest

from src.research.indicator_library import FAMILIES, signal_series, specifications


def bars(length=320):
    result = []
    for index in range(length):
        close = 100 + 8 * math.sin(index / 5) + index * 0.05
        result.append({"ts": f"2024-01-{1 + index // 24:02d} {index % 24:02d}:00:00",
                       "open": close - 0.3, "high": close + 1.0,
                       "low": close - 1.0, "close": close, "volume": 1000})
    return result


class IndicatorLibraryTests(unittest.TestCase):
    def test_exactly_100_distinct_preregistered_rules(self):
        specs = specifications()
        self.assertEqual(len(specs), 100)
        self.assertEqual({spec["family"] for spec in specs}, set(FAMILIES))
        self.assertEqual(len({spec["rule_id"] for spec in specs}), 100)
        for family in FAMILIES:
            self.assertEqual(sum(spec["family"] == family for spec in specs), 10)

    def test_signal_history_does_not_change_when_future_bar_is_appended(self):
        history = bars()
        future = {"ts": "2024-02-01 00:00:00", "open": 180, "high": 200,
                  "low": 40, "close": 190, "volume": 10000}
        for spec in specifications():
            with self.subTest(rule=spec["rule_id"]):
                previous = signal_series(history, spec)
                appended = signal_series(history + [future], spec)
                self.assertEqual(len(previous), len(history))
                self.assertEqual(previous, appended[:-1])
                self.assertTrue(set(previous) <= {-1, 0, 1})

    def test_donchian_breakout_excludes_current_bar_from_channel(self):
        sample = bars(40)
        for bar in sample:
            bar.update(open=100, high=101, low=99, close=100)
        sample[30].update(high=112, close=110)
        rule = next(spec for spec in specifications()
                    if spec["family"] == "donchian_breakout" and spec["parameters"]["period"] == 5)
        result = signal_series(sample, rule)
        self.assertEqual(result[30], 1)
        self.assertEqual(result[31], 0)


if __name__ == "__main__":
    unittest.main()
