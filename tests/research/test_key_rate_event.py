"""Scheduled events cannot enter before the first full post-release bar closes."""

import unittest

from src.research.key_rate_event import (decision_outcome_rows, decision_side,
                                         decision_signals, event_signals,
                                         matched_event_rows)


class KeyRateEventTests(unittest.TestCase):
    def setUp(self):
        self.bars = [
            {"ts": f"2024-02-16 {hour:02}:00:00", "open": 100.0,
             "close": 101.0 if hour == 14 else 100.0, "volume": 1000.0}
            for hour in range(10, 20)]

    def test_signal_after_complete_hour_and_next_open_exit(self):
        entries, exits = event_signals(self.bars, {"2024-02-16"}, "continuation", 3)
        self.assertEqual(entries.index(1), 4)
        self.assertEqual(exits.index(-1), 7)
        self.assertTrue(all(x == 0 for x in entries[:4]))

    def test_missing_next_hour_drops_signal(self):
        bars = [bar for bar in self.bars if bar["ts"] != "2024-02-16 15:00:00"]
        entries, _ = event_signals(bars, {"2024-02-16"}, "continuation", 1)
        self.assertFalse(any(entries))

    def test_event_study_requires_matched_hour(self):
        rows, missing = matched_event_rows("TEST", self.bars, {"2024-02-16"})
        self.assertFalse(rows)
        self.assertEqual(missing[0]["reason"], "missing_14_or_15_or_matched_hour")

    def test_published_rate_not_candle_sets_direction(self):
        decision = {"2024-02-16": {"previous_rate": 16, "announced_rate": 18}}
        entries, exits = decision_signals(self.bars, decision, "conventional", 1)
        self.assertEqual(entries[4], -1)
        self.assertEqual(exits[5], 1)
        self.assertEqual(decision_side(16, 18, "inverse"), 1)
        self.assertEqual(decision_side(16, 16, "conventional"), 0)
        self.assertEqual(decision_side(16, 16, "hold_long"), 1)
        self.assertEqual(decision_side(16, 16, "hold_short"), -1)
        rows = decision_outcome_rows("TEST", self.bars, decision, "conventional", 1)
        self.assertEqual(rows[0]["rate_change_bp"], 200)


if __name__ == "__main__":
    unittest.main()
