import importlib.util
import math
import unittest
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate

MODULE = Path(__file__).resolve().parents[2] / "experiments/single-indicator/htf-level-breakouts/levels.py"
SPEC = importlib.util.spec_from_file_location("htf_level_breakouts", MODULE)
LEVELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEVELS)


def bar(day, close=100, high=101, low=99):
    return {"ts": f"2024-01-{day:02d} 10:00:00", "open": close,
            "high": high, "low": low, "close": close, "volume": 1}


class HtfLevelBreakoutTests(unittest.TestCase):
    def test_current_day_is_excluded_from_daily_level(self):
        daily = [bar(1, high=104), bar(2, high=106), bar(3, high=108), bar(4, high=1000)]
        signal = [bar(4)]
        self.assertEqual(LEVELS.levels(signal, daily, "1D", 3), [(108, 99)])
        daily[-1]["high"] = 9999
        self.assertEqual(LEVELS.levels(signal, daily, "1D", 3), [(108, 99)])

    def test_current_week_is_excluded_from_weekly_level(self):
        daily = [bar(1, high=104), bar(8, high=106), bar(15, high=108), bar(22, high=1000)]
        self.assertEqual(LEVELS.levels([bar(22)], daily, "1W", 2), [(108, 99)])
        daily[-1]["high"] = 9999
        self.assertEqual(LEVELS.levels([bar(22)], daily, "1W", 2), [(108, 99)])

    def test_breakout_then_later_retest_and_false_break(self):
        bars = [bar(1, high=101, low=99) for _ in range(20)]
        for index in range(20):
            bars[index]["ts"] = f"2024-01-{1+index//10:02d} {index%10+10:02d}:00:00"
        bars[17].update(close=103, high=104, low=101)
        bars[18].update(close=103, high=104, low=102)
        boundaries = [(102, 98)] * len(bars)
        breaks = LEVELS.breakout_events(bars, boundaries, 0, min_width_atr=0)
        self.assertEqual(breaks[17], 1)
        retests = LEVELS.retest_events(bars, boundaries, breaks)
        self.assertEqual(retests[17], 0)
        self.assertEqual(retests[18], 1)
        bad = [dict(item) for item in bars]
        bad[18]["close"] = 101
        bad[19].update(close=103, high=104, low=102)
        false_retests = LEVELS.retest_events(bad, boundaries, breaks)
        self.assertEqual(false_retests[18:], [0, 0])

    def test_entry_from_closed_signal_is_next_bar(self):
        bars = [bar(1, high=101, low=99) for _ in range(40)]
        for index, item in enumerate(bars):
            item["ts"] = f"2024-01-{1+index//10:02d} {index%10+10:02d}:00:00"
        signal = [0] * 40
        signal[34] = 1
        signal[37] = -1
        curve = []
        simulate(bars, signal, [True]*40, [True]*40, 0, "2024-01-01",
                 fee_bps=0, equity_curve=curve)
        self.assertEqual(curve[34-33]["position"], 0)
        self.assertGreater(curve[35-33]["position"], 0)


if __name__ == "__main__":
    unittest.main()
