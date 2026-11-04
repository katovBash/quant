import importlib.util
import unittest
from pathlib import Path


STRATEGY = Path(__file__).resolve().parents[2] / "strategies/ema-cross-13-48-long-short-1h/strategy.py"
spec = importlib.util.spec_from_file_location("ema_13_48_strategy", STRATEGY)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FixedSignalTests(unittest.TestCase):
    def test_waits_for_completed_history(self):
        self.assertIsNone(module.target_side([100.0] * 49, "long_short", 0))

    def test_long_and_short_crossings(self):
        upward = [100.0] * 50 + [200.0]
        downward = [100.0] * 50 + [200.0] * 50 + [50.0]
        self.assertEqual(module.target_side(upward, "long_short", 0), "long")
        self.assertEqual(module.target_side(downward, "long_short", 1), "short")

    def test_direction_mode_closes_opposite_without_opening(self):
        upward = [100.0] * 50 + [200.0]
        self.assertEqual(module.target_side(upward, "short", -1), "flat")
        self.assertIsNone(module.target_side(upward, "short", 0))


if __name__ == "__main__":
    unittest.main()
