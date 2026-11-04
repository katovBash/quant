"""A repeated same-side paper signal must not close and reopen a position."""

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from service.data_sources.moex import normalize_bars
from service.paper_runner import advance


class LineRetestPaperTests(unittest.TestCase):
    def test_same_side_signal_keeps_existing_position(self):
        start = datetime(2026, 1, 1, tzinfo=ZoneInfo("Europe/Moscow"))
        raw = [{"begin": (start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                "open": 100, "high": 101, "low": 99, "close": 100}
               for i in range(204)]
        now = start + timedelta(days=10)
        opts = {"symbol": "TEST", "capital": 1_000_000, "mode": "long_short",
                "fee_bps": 5, "slip_bps": 10, "borrow_bps": 0,
                "lot_size": 1, "history_from": "2026-01-01",
                "position_weight": 0.10, "strategy_id": "review-rule",
                "strategy_module": SimpleNamespace(signal=lambda bars: "long"),
                "min_bars": 200}
        state = None
        all_events = []
        for count in (200, 201, 202, 203):
            state, events, _ = advance(state, normalize_bars(raw[:count], now),
                                       now.isoformat(), **opts)
            all_events.extend(event["action"] for event in events)
        self.assertEqual(all_events, ["OPEN_LONG"])
        self.assertGreater(state["position"], 0)


if __name__ == "__main__":
    unittest.main()
