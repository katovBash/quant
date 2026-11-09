"""A future candle cannot change already emitted ZigZag breakout events."""

import unittest
from unittest.mock import patch

from src.research.zigzag_signals import (
    breakout_signals, compression_signals, confirmed_pivots, retest_signals,
    trendline_signals, third_touch_signals, parallel_second_touch_signals,
    confirmed_channel_bounce_signals,
)


class ZigZagSignalTests(unittest.TestCase):
    def setUp(self):
        self.bars = []
        for i in range(70):
            center = 100 + (i % 9 - 4) * 2 + i * 0.03
            self.bars.append({"open": center - 0.3, "high": center + 1,
                              "low": center - 1, "close": center})

    def test_pivot_is_available_only_after_right_wing(self):
        for confirmed_at, pivot_at, _, _ in confirmed_pivots(self.bars, 3, 2):
            self.assertGreaterEqual(confirmed_at - pivot_at, 3)

    def test_two_highs_and_one_middle_low_define_tradable_lower_boundary(self):
        values = [(91, 85, 88), (100, 95, 98), (96, 90, 91),
                  (90, 80, 85), (95, 88, 93), (97, 90, 94),
                  (93, 86, 88), (90, 82, 85), (92, 76, 80),
                  (95, 86, 90), (92, 84, 88)]
        bars = [{"ts": f"2026-01-{i+1:02d} 00:00:00", "open": close,
                 "high": high, "low": low, "close": close}
                for i, (high, low, close) in enumerate(values)]
        trace = []
        entries, _ = confirmed_channel_bounce_signals(
            bars, 1, 2, 0.5, 50, trace=trace, start="2026-01-01")
        self.assertEqual(entries[:8], [0] * 8)
        self.assertEqual(entries[8], 1)  # support line parallel to two confirmed highs
        self.assertEqual(entries[9], -1)  # resistance rejection
        self.assertEqual(trace[7]["base_side"], "high")
        for cutoff in (6, 8, 9, 10):
            prefix = confirmed_channel_bounce_signals(
                bars[:cutoff], 1, 2, 0.5, 50, start="2026-01-01")
            self.assertEqual(tuple(part[:cutoff] for part in (entries, _)), prefix)

    def test_prefix_signals_do_not_repaint(self):
        factories = (
            lambda bars, wing, deviation: breakout_signals(bars, wing, deviation),
            lambda bars, wing, deviation: retest_signals(bars, wing, deviation, 0.5),
            lambda bars, wing, deviation: trendline_signals(bars, wing, deviation, 50),
            lambda bars, wing, deviation: compression_signals(bars, wing, deviation, 25),
            lambda bars, wing, deviation: third_touch_signals(bars, wing, deviation, 0.5, 50, "bounce"),
            lambda bars, wing, deviation: third_touch_signals(bars, wing, deviation, 0.5, 50, "breakout"),
        )
        for factory in factories:
            for wing in (2, 3, 5):
                for deviation in (2, 4, 6):
                    full = factory(self.bars, wing, deviation)
                    for cutoff in (25, 40, 60):
                        prefix = factory(self.bars[:cutoff], wing, deviation)
                        self.assertEqual(tuple(part[:cutoff] for part in full), prefix)

    def test_third_contact_waits_for_second_pivot_confirmation(self):
        bars = [{"open": 10.5, "high": 11, "low": 10.2, "close": 10.5}
                for _ in range(10)]
        bars[6] = {"open": 10.4, "high": 10.8, "low": 9.98, "close": 10.2}
        anchors = [(2, 1, "low", 10), (5, 4, "low", 10)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            entries, _ = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce")
        self.assertEqual(entries[:6], [0] * 6)
        self.assertEqual(entries[6], 1)
        self.assertEqual(sum(bool(value) for value in entries), 1)
        bars[6] = {"open": 10.4, "high": 10.8, "low": 9.8, "close": 9.8}
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            entries, _ = third_touch_signals(bars, 1, 2, 0.5, 50, "breakout")
        self.assertEqual(entries[6], -1)

    def test_parallel_channel_uses_first_high_then_second_contact(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 11,
                 "high": 11.5, "low": 10.5, "close": 11} for i in range(1, 11)]
        bars[6].update({"high": 12.02, "close": 11.6})
        bars[7].update({"low": 9.98, "close": 10.2})
        pivots = [(2, 1, "low", 10), (4, 3, "low", 10), (5, 4, "high", 12)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(pivots)):
            entries, exits = parallel_second_touch_signals(bars, 1, 2, 0.5, 50)
        self.assertEqual(entries[:6], [0] * 6)
        self.assertEqual(entries[6], -1)
        self.assertEqual(exits[7], 1)

    def test_parallel_channel_prefix_does_not_repaint(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 10,
                 "high": 12 + i % 3, "low": 9 + i % 3,
                 "close": 10 + i % 3} for i in range(1, 21)]
        full = parallel_second_touch_signals(bars, 2, 2, 0.5, 50)
        for cutoff in (10, 15):
            prefix = parallel_second_touch_signals(bars[:cutoff], 2, 2, 0.5, 50)
            self.assertEqual(tuple(part[:cutoff] for part in full), prefix)

    def test_parallel_channel_support_side_opens_long(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 11,
                 "high": 11.5, "low": 10.5, "close": 11} for i in range(1, 10)]
        bars[6].update({"low": 9.98, "close": 10.3})
        pivots = [(2, 1, "high", 12), (4, 3, "high", 12), (5, 4, "low", 10)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(pivots)):
            entries, _ = parallel_second_touch_signals(bars, 1, 2, 0.5, 50)
        self.assertEqual(entries[6], 1)

    def test_parallel_daily_anchor_waits_until_next_date(self):
        higher = [{"ts": f"2026-01-{i:02d} 00:00:00", "high": 12,
                   "low": 10, "close": 11} for i in range(1, 8)]
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 11,
                 "high": 12.02, "low": 10.5, "close": 11.6} for i in range(1, 9)]
        pivots = [(2, 1, "low", 10), (4, 3, "low", 10), (5, 4, "high", 12)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(pivots)):
            entries, _ = parallel_second_touch_signals(bars, 1, 2, 0.5, 50,
                                                         line_bars=higher)
        self.assertEqual(entries[5], 0)
        self.assertEqual(entries[6], -1)

    def test_daily_line_is_not_visible_during_confirmation_day(self):
        higher = [{"ts": f"2026-01-0{i} 00:00:00", "high": 11, "low": 10, "close": 10.5}
                  for i in range(1, 5)]
        bars = [{"ts": f"2026-01-0{i} 12:00:00", "open": 10.5,
                 "high": 11, "low": 10.2, "close": 10.5}
                for i in range(1, 7)]
        bars[3]["low"] = 9.98  # confirmation day: must not see the daily line
        bars[4]["low"] = 9.98
        anchors = [(1, 0, "low", 10), (3, 2, "low", 10)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            entries, _ = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce", line_bars=higher)
        self.assertEqual(entries[3], 0)
        self.assertEqual(entries[4], 1)

    def test_higher_line_prefix_does_not_repaint(self):
        higher = [{"ts": f"2026-01-{i:02d} 00:00:00", "high": 11 + i % 3,
                   "low": 9 + i % 3, "close": 10 + i % 3}
                  for i in range(1, 21)]
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 10 + i % 3,
                 "high": 11 + i % 3, "low": 9 + i % 3, "close": 10 + i % 3}
                for i in range(1, 21)]
        full = third_touch_signals(bars, 2, 2, 0.5, 50, "bounce", line_bars=higher)
        for cutoff in (10, 15):
            prefix = third_touch_signals(bars[:cutoff], 2, 2, 0.5, 50, "bounce",
                                         line_bars=higher)
            self.assertEqual(tuple(part[:cutoff] for part in full), prefix)

    def test_take_profit_trigger_is_after_entry_fill(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 10.5,
                 "high": 11, "low": 10.2, "close": 10.5}
                for i in range(1, 11)]
        bars[6]["low"], bars[6]["close"] = 9.98, 10.2
        bars[7]["high"] = 11.1
        anchors = [(2, 1, "low", 10), (5, 4, "low", 10)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            entries, exits = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce",
                                                 exit_mode="tp_5", start="2026-01-01")
        self.assertEqual(entries[6], 1)
        self.assertEqual(exits[6], 1)
        self.assertEqual(exits[7], -1)

    def test_daily_trend_filter_requires_rising_support(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 10,
                 "high": 11, "low": 9.5, "close": 10} for i in range(1, 11)]
        bars[6].update({"open": 9, "high": 9.4, "low": 8.32, "close": 8.8})
        anchors = [(2, 1, "low", 10), (5, 4, "low", 9)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            unrestricted, _ = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce")
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            trend_only, _ = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce",
                                                slope_mode="trend")
        self.assertEqual(unrestricted[6], 1)
        self.assertEqual(trend_only[6], 0)

    def test_atr_target_uses_only_completed_bars_at_entry(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 10.5,
                 "high": 11, "low": 10.2, "close": 10.5} for i in range(1, 21)]
        bars[16]["low"], bars[16]["close"] = 9.98, 10.2
        bars[17]["high"] = 11.5
        bars[18]["high"] = 12.4
        anchors = [(2, 1, "low", 10), (5, 4, "low", 10)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            entries, exits = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce",
                                                 exit_mode="tp_atr_2", start="2026-01-01")
        self.assertEqual(entries[16], 1)
        self.assertEqual(exits[17], 0)
        self.assertEqual(exits[18], -1)
        for cutoff in (17, 18):
            with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
                prefix = third_touch_signals(bars[:cutoff], 1, 2, 0.5, 50, "bounce",
                                             exit_mode="tp_atr_2", start="2026-01-01")
            self.assertEqual((entries[:cutoff], exits[:cutoff]), prefix)

    def test_opposite_resistance_touch_closes_long(self):
        bars = [{"ts": f"2026-01-{i:02d} 12:00:00", "open": 10.5,
                 "high": 11, "low": 10.2, "close": 10.5}
                for i in range(1, 11)]
        bars[6]["low"], bars[6]["close"] = 9.98, 10.2
        bars[7]["high"], bars[7]["close"] = 11.95, 12.1
        anchors = [(2, 1, "low", 10), (3, 2, "high", 12),
                   (4, 3, "low", 10), (5, 4, "high", 12)]
        with patch("src.research.zigzag_signals.confirmed_pivots", return_value=iter(anchors)):
            entries, exits = third_touch_signals(bars, 1, 2, 0.5, 50, "bounce",
                                                 exit_mode="opposite_line", start="2026-01-01")
        self.assertEqual(entries[6], 1)
        self.assertEqual(entries[7], 0)
        self.assertEqual(exits[7], -1)


if __name__ == "__main__":
    unittest.main()
