import importlib.util
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "experiments/market-regime-grid-search/transition.py"
SPEC = importlib.util.spec_from_file_location("phase_transition", MODULE_PATH)
transition = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(transition)


class PhaseTransitionTests(unittest.TestCase):
    def test_first_breach_wins_and_uses_frozen_bounds(self):
        bars = [{"close": price} for price in (100, 103, 97, 101)]
        self.assertEqual(transition.first_breakout(bars, 0, 3, 98, 102), "up")
        self.assertEqual(transition.first_breakout(bars, 1, 2, 98, 102), "down")
        self.assertEqual(transition.first_breakout(bars, 2, 1, 98, 102), "no_break")

    def test_regression_slope_only_uses_prior_closes(self):
        bars = [{"close": float(i)} for i in range(25)]
        slope = transition.channel_slope_atr(bars, 20, 20, 2)
        bars[20]["close"] = 10_000
        self.assertEqual(slope, transition.channel_slope_atr(bars, 20, 20, 2))
        self.assertAlmostEqual(slope, 0.5)

    def test_summary_preserves_episode_count(self):
        base = {"symbol": "TEST", "timeframe": "1D", "sample": "holdout", "horizon": 5,
                "duration_bin": "0-1d", "channel_position": "upper", "slope_bin": "up",
                "weekday": 1}
        events = [{**base, "episode_start": "a", "outcome": "up"},
                  {**base, "episode_start": "a", "outcome": "no_break"},
                  {**base, "episode_start": "b", "outcome": "down"}]
        row = next(x for x in transition.summarize_events(events) if x["feature"] == "all")
        self.assertEqual(row["observations"], 3)
        self.assertEqual(row["episode_count"], 2)
        self.assertAlmostEqual(row["up_pct"], 33.33)

    def test_slope_control_is_matched_on_channel_position(self):
        base = {"symbol": "TEST", "timeframe": "1H", "sample": "holdout", "horizon": 5,
                "duration_bin": "0-1d", "weekday": 1}
        events = [{**base, "episode_start": "a", "channel_position": "upper",
                   "slope_bin": "up", "outcome": "up"},
                  {**base, "episode_start": "b", "channel_position": "upper",
                   "slope_bin": "flat", "outcome": "no_break"},
                  {**base, "episode_start": "c", "channel_position": "lower",
                   "slope_bin": "flat", "outcome": "down"}]
        row = next(x for x in transition.summarize_events(events)
                   if x["feature"] == "slope_within_position" and x["bucket"] == "upper|up")
        self.assertEqual(row["baseline_group"], "same_channel_position")
        self.assertEqual(row["up_pct"], 100.0)
        self.assertEqual(row["baseline_up_pct"], 50.0)

    def test_zone_keeps_frozen_bounds_across_multiple_days(self):
        from datetime import date, timedelta
        days = [date(2026, 1, 1) + timedelta(days=i) for i in range(40)]
        bars = [{"ts": f"{day.isoformat()} 12:00:00", "open": 100.0,
                 "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000}
                for day in days]
        protocol = json.loads(transition.PROTOCOL.read_text())
        events = transition.events_for_series(bars, "TEST", "1D", protocol)
        five = [event for event in events if event["horizon"] == 5]
        self.assertTrue(five)
        self.assertEqual(len({event["episode_start"] for event in five}), 1)
        self.assertTrue(any(event["age_days"] >= 6 for event in five))

    def test_future_change_cannot_change_earlier_channel_features(self):
        from datetime import date, timedelta
        days = [date(2026, 1, 1) + timedelta(days=i) for i in range(50)]
        bars = [{"ts": f"{day.isoformat()} 12:00:00", "open": 100.0,
                 "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000}
                for day in days]
        protocol = json.loads(transition.PROTOCOL.read_text())
        first = transition.events_for_series(bars, "TEST", "1D", protocol)
        changed = [dict(bar) for bar in bars]
        changed[-1]["close"] = 200.0
        second = transition.events_for_series(changed, "TEST", "1D", protocol)
        early = lambda rows: [tuple(row[key] for key in ("ts", "episode_start", "age_days",
                            "channel_position", "channel_slope_atr_per_bar", "weekday"))
                              for row in rows if row["ts"] < "2026-02-10"]
        self.assertEqual(early(first), early(second))


if __name__ == "__main__":
    unittest.main()
