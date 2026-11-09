"""Weekly paper signals wait for the full trading week, including Saturday."""

import unittest
from types import SimpleNamespace

from service.paper_runner import advance, initial_state


class WeeklyPaperTests(unittest.TestCase):
    def test_saturday_is_in_week_and_order_fills_next_monday_open(self):
        prices = [("2026-11-05", 100, 101), ("2026-11-06", 101, 102),
                  ("2026-11-07", 102, 103), ("2026-11-09", 110, 111)]
        bars = [dict(ts=day + " 00:00:00", end=day + "T23:59:59+03:00",
                     open=opening, high=max(opening, closing),
                     low=min(opening, closing), close=closing, volume=1)
                for day, opening, closing in prices]
        observed = []
        module = SimpleNamespace(weekly_signal=lambda weeks: observed.append(weeks[-1]["ts"]) or "long")
        kwargs = dict(symbol="TEST", capital=1_000_000, mode="long_short",
                      fee_bps=5, slip_bps=10, borrow_bps=0, lot_size=1,
                      history_from="2022-01-01", position_weight=0.1,
                      strategy_id="test-weekly", timeframe="1W",
                      strategy_module=module, min_bars=2)
        state = initial_state("TEST", bars[:2], "2026-11-08T09:00:00+03:00",
                              1_000_000, "long_short", 5, 10, 0, 1,
                              "2022-01-01", 0.1, "test-weekly", "1W", 2)
        state, events, _ = advance(state, bars[:3], "2026-11-08T09:00:00+03:00", **kwargs)
        self.assertEqual(events, [])
        self.assertEqual(observed, [])
        state, events, _ = advance(state, bars, "2026-11-10T09:00:00+03:00", **kwargs)
        self.assertEqual(observed, ["2026-11-07 00:00:00"])
        self.assertEqual([event["action"] for event in events], ["OPEN_LONG"])
        self.assertEqual(events[0]["signal_bar"], "2026-11-07 00:00:00")
        self.assertEqual(events[0]["fill_bar"], "2026-11-09 00:00:00")
        self.assertAlmostEqual(events[0]["price"], 110 * 1.001)


if __name__ == "__main__":
    unittest.main()
