import unittest

from src.ema.core.hybrid_ema import target_position


class SignalTests(unittest.TestCase):
    def test_long_entry_and_exit(self):
        self.assertEqual(target_position([9, 11], [10, 10], [12, 12], 1, 0), 1)
        self.assertEqual(target_position([11, 9], [10, 10], [12, 12], 1, 1), 0)

    def test_short_entry_and_exit(self):
        self.assertEqual(target_position([7, 7], [11, 9], [10, 10], 1, 0), -1)
        self.assertEqual(target_position([7, 7], [9, 11], [10, 10], 1, -1), 0)

    def test_opposite_entry_reverses(self):
        self.assertEqual(target_position([9, 11], [10, 10], [12, 12], 1, -1), 1)
        self.assertEqual(target_position([7, 7], [11, 9], [10, 10], 1, 1), -1)

    def test_conflicting_entries_flatten(self):
        self.assertEqual(target_position([9, 11], [11, 9], [10, 10], 1, 1), 0)

    def test_trend_long_requires_12_above_33(self):
        self.assertEqual(target_position([9, 11], [10, 10], [12, 12], 1, 0,
                                         "trend_long"), 0)
        self.assertEqual(target_position([9, 11], [10, 10], [8, 8], 1, 0,
                                         "trend_long"), 1)

    def test_trend_long_uses_slow_exit_and_reverses(self):
        self.assertEqual(target_position([11, 9], [10, 10], [8, 8], 1, 1,
                                         "trend_long"), 1)
        self.assertEqual(target_position([7, 7], [11, 9], [10, 10], 1, 1,
                                         "trend_long"), -1)
        self.assertEqual(target_position([7, 7], [9, 11], [10, 10], 1, -1,
                                         "trend_long"), 0)

    def test_symmetric_12_33_reverses_on_both_crosses(self):
        self.assertEqual(target_position([7, 7], [9, 11], [10, 10], 1, -1,
                                         "symmetric_12_33"), 1)
        self.assertEqual(target_position([7, 7], [11, 9], [10, 10], 1, 1,
                                         "symmetric_12_33"), -1)


if __name__ == "__main__":
    unittest.main()
