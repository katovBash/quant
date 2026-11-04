import copy
import math
import unittest

from src.research.ema_zone_lines import (higher_lines, higher_range_zones, line_ema_gates,
                                         line_retest_signals, pivot_history)


def daily_bars():
    highs = [101, 103, 108, 104, 102, 105, 110, 106, 103, 104, 109, 105]
    lows = [98, 96, 94, 97, 99, 95, 93, 96, 100, 97, 92, 98]
    return [{"ts": f"2024-01-{i+1:02d} 00:00:00", "open": 100,
             "high": highs[i], "low": lows[i], "close": 100, "volume": 1}
            for i in range(len(highs))]


class EmaZoneLinesTests(unittest.TestCase):
    def test_daily_outer_zone_uses_only_completed_days(self):
        daily = [{"ts": f"2026-01-{day:02d} 00:00:00", "high": 110 + day % 3,
                  "low": 90 - day % 2, "close": 100, "open": 100, "volume": 1}
                 for day in range(1, 22)]
        signal = [{"ts": "2026-01-21 12:00:00"}]
        before = higher_range_zones(signal, daily, "1D", 20)
        changed = copy.deepcopy(daily)
        changed[-1]["high"], changed[-1]["low"] = 1000, 1
        self.assertEqual(before, higher_range_zones(signal, changed, "1D", 20))
        self.assertEqual(before, [(112, 89)])

    def test_retest_needs_separated_outer_boundaries_when_requested(self):
        bars = [{"ts": f"2026-01-{1+i//10:02d} {i%10+10:02d}",
                 "open": 100, "high": 101, "low": 99, "close": 100}
                for i in range(45)]
        lines = [(101.0, 99.0)] * len(bars)
        self.assertEqual(sum(bool(x) for x in line_retest_signals(
            bars, lines, 0.5, "none", min_channel_atr=4)), 0)

    def test_current_four_hour_bucket_cannot_change_hourly_signal_line(self):
        highs = [101, 103, 108, 104, 102, 105, 110, 106, 103, 104, 109, 105]
        lows = [98, 96, 94, 97, 99, 95, 93, 96, 100, 97, 92, 98]
        hourly = []
        for bucket in range(12):
            day, first_hour = 1 + bucket // 2, 9 if bucket % 2 == 0 else 13
            for hour in range(first_hour, first_hour + 4):
                hourly.append({"ts": f"2024-01-{day:02d} {hour:02d}:00:00",
                               "open": 100, "high": highs[bucket], "low": lows[bucket],
                               "close": 100, "volume": 1})
        signal = [hourly[-1]]
        before = higher_lines(signal, [], "4H", hourly=hourly)
        altered = copy.deepcopy(hourly)
        for bar in altered[-4:]:
            bar["high"], bar["low"] = 1000, 1
        after = higher_lines(signal, [], "4H", hourly=altered)
        self.assertEqual(before, after)
        self.assertTrue(all(math.isfinite(value) for value in before[0]))

    def test_daily_signal_excludes_all_four_hour_bars_from_its_day(self):
        hourly = []
        for day in range(1, 8):
            for hour in range(9, 17):
                level = 100 + (day % 3) * 4
                hourly.append({"ts": f"2024-01-{day:02d} {hour:02d}:00:00",
                               "open": 100, "high": level + 2, "low": level - 6,
                               "close": 100, "volume": 1})
        signal = [{"ts": "2024-01-07 00:00:00"}]
        before = higher_lines(signal, [], "4H", hourly=hourly)
        altered = copy.deepcopy(hourly)
        for bar in altered[-8:]:
            bar["high"], bar["low"] = 1000, 1
        self.assertEqual(before, higher_lines(signal, [], "4H", hourly=altered))

    def test_pivots_require_closed_right_wing(self):
        history = pivot_history(daily_bars(), 2)
        self.assertEqual(history[3][0], [])
        self.assertEqual(history[4][0], [(2, 108)])

    def test_current_daily_bar_cannot_change_intraday_lines(self):
        daily = daily_bars()
        intraday = [{"ts": "2024-01-12 13:00:00", "open": 100, "high": 101,
                     "low": 99, "close": 100}]
        before = higher_lines(intraday, daily, "1D")
        altered = copy.deepcopy(daily)
        altered[-1]["high"] = 1000
        altered[-1]["low"] = 1
        after = higher_lines(intraday, altered, "1D")
        self.assertEqual(before, after)
        self.assertTrue(all(math.isfinite(x) for x in before[0]))

    def test_future_intraday_bar_cannot_change_prior_gates(self):
        bars = [{"ts": f"2024-01-{1+i//10:02d} {i%10+10:02d}:00:00",
                 "open": 100+i/10, "high": 101+i/10,
                 "low": 99+i/10, "close": 100+i/10} for i in range(45)]
        lines = [(106.0, 98.0)] * len(bars)
        up, down = line_ema_gates(bars, lines, 1.0, 1)
        extra = {"ts": "2024-01-06 10:00:00", "open": 500, "high": 501,
                 "low": 499, "close": 500}
        more_up, more_down = line_ema_gates(bars + [extra], lines + [(106.0, 98.0)], 1.0, 1)
        self.assertEqual((up, down), (more_up[:len(bars)], more_down[:len(bars)]))

    def test_line_retest_fires_on_first_rejection_then_waits_for_new_approach(self):
        bars = [{"ts": f"2024-01-{1+i//10:02d} {i%10+10:02d}:00:00",
                 "open": 100, "high": 101, "low": 100, "close": 100}
                for i in range(48)]
        for index in (40, 41, 43):
            bars[index]["low"] = 99
        lines = [(110.0, 99.0)] * len(bars)
        signals = line_retest_signals(bars, lines, 0.5, "none")
        self.assertEqual([index for index, signal in enumerate(signals) if signal == 1],
                         [40, 43])
        self.assertEqual(line_retest_signals(bars + [dict(bars[-1])],
                                               lines + [lines[-1]], 0.5, "none")[:len(bars)],
                         signals)


if __name__ == "__main__":
    unittest.main()
