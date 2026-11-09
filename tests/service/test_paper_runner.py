"""A virtual executor must never replay old signals or duplicate a fill."""

import unittest
import io
import json
from types import SimpleNamespace
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from service.data_sources.moex import MarketDataUnavailable, fetch_candles
from service.paper_runner import advance, normalize_bars, poll_error, side_from_strategy, write_evaluation_files


class PaperRunnerTests(unittest.TestCase):
    def test_position_aware_rule_can_request_exit(self):
        seen = []
        module = SimpleNamespace(USES_POSITION=True,
                                 signal=lambda bars, position: seen.append(position) or "flat")
        result = side_from_strategy(module, [{"close": 100}], "long_short", 10)
        self.assertEqual(result, "flat")
        self.assertEqual(seen, [10])

    def setUp(self):
        start = datetime(2027, 1, 1, tzinfo=ZoneInfo("Europe/Moscow"))
        prices = [100] * 40 + [110, 111, 50, 49]
        self.raw = [dict(begin=(start + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                         end=(start + timedelta(hours=i + 1)).strftime("%Y-%m-%d %H:%M:%S"),
                         close=p) for i, p in enumerate(prices)]
        self.now = start + timedelta(days=3)
        self.opts = dict(symbol="TEST", capital=1_000_000, mode="long_short",
                         fee_bps=5, slip_bps=10, borrow_bps=0,
                         lot_size=1, history_from="2027-01-01", position_weight=0.10,
                         strategy_id="test-rule", timeframe="1H",
                         strategy_module=SimpleNamespace(target_side=lambda closes, mode, position:
                             "long" if closes[-1] >= 110 else "short" if closes[-1] <= 50 else None))

    def step(self, state, n):
        bars = normalize_bars(self.raw[:n], self.now)
        return advance(state, bars, self.now.isoformat(), **self.opts)

    def test_first_run_seeds_without_old_trades(self):
        state, events, point = self.step(None, 41)
        self.assertEqual(events, [])
        self.assertIsNone(point)
        self.assertEqual(state["position"], 0)
        self.assertEqual(state["strategy"], "test-rule")
        self.assertEqual(state["initial_capital"], 1_000_000)
        self.assertEqual(state["position_weight"], 0.10)
        self.assertEqual(state["lot_size"], 1)
        self.assertIsNone(state["pending"])

    def test_signal_fills_only_after_later_observed_candle_and_is_idempotent(self):
        state, _, _ = self.step(None, 40)
        state, events, _ = self.step(state, 41)
        self.assertEqual(events, [])
        self.assertEqual(state["pending"]["side"], "long")
        state, events, _ = self.step(state, 42)
        self.assertEqual([e["action"] for e in events], ["OPEN_LONG"])
        self.assertEqual(events[0]["price"], 111 * 1.001)
        same, events, point = self.step(state, 42)
        self.assertIs(same, state)
        self.assertEqual(events, [])
        self.assertIsNone(point)
        state, _, _ = self.step(state, 43)
        self.assertEqual(state["pending"]["side"], "short")
        state, events, _ = self.step(state, 44)
        self.assertEqual([e["action"] for e in events], ["CLOSE_LONG", "OPEN_SHORT"])
        self.assertEqual(state["closed_trades"], 1)
        self.assertLess(state["position"], 0)

    def test_gap_replays_each_completed_candle_in_order(self):
        state, _, _ = self.step(None, 40)
        state, _, _ = self.step(state, 41)
        state, events, _ = self.step(state, 44)
        self.assertEqual([e["action"] for e in events],
                         ["GAP", "OPEN_LONG", "CLOSE_LONG", "OPEN_SHORT"])
        self.assertLess(state["position"], 0)
        self.assertEqual(events[1]["fill_bar"], self.raw[41]["begin"])
        self.assertEqual(events[-1]["fill_bar"], self.raw[43]["begin"])
        self.assertTrue(events[1]["recovered_after_gap"])
        self.assertEqual(state["equity_log"][-3]["bar_ts"], self.raw[41]["begin"])
        self.assertEqual(state["gap_count"], 1)

    def test_evaluator_exports_only_dates_after_freeze(self):
        state, _, _ = self.step(None, 40)
        for n in range(41, 45):
            state, _, _ = self.step(state, n)
        state["started_at"] = "2027-01-01T00:00:00+03:00"
        with TemporaryDirectory() as tmp:
            write_evaluation_files(Path(tmp), state)
            self.assertIn("2027-01-02", (Path(tmp) / "closed_trades.csv").read_text())
            self.assertIn("2027-01-02", (Path(tmp) / "equity.csv").read_text())
            self.assertNotIn("2027-01-04", (Path(tmp) / "equity.csv").read_text())

    def test_capital_cannot_change_after_start(self):
        state, _, _ = self.step(None, 40)
        self.opts["capital"] = 2_000_000
        with self.assertRaisesRegex(ValueError, "initial_capital"):
            self.step(state, 41)

    def test_position_weight_cannot_change_after_start(self):
        state, _, _ = self.step(None, 40)
        self.opts["position_weight"] = 0.25
        with self.assertRaisesRegex(ValueError, "position_weight"):
            self.step(state, 41)

    def test_existing_twenty_five_percent_account_can_continue(self):
        self.opts["position_weight"] = 0.25
        state, _, _ = self.step(None, 40)
        updated, _, _ = self.step(state, 41)
        self.assertEqual(updated["position_weight"], 0.25)

    def test_iss_last_trade_end_does_not_confirm_live_candle(self):
        opening = "2027-01-05 10:00:00"
        row = {"begin": opening, "end": "2027-01-05 10:07:12", "close": 100}
        msk = ZoneInfo("Europe/Moscow")
        self.assertEqual(normalize_bars([row], datetime(2027, 1, 5, 10, 30, tzinfo=msk)), [])
        self.assertEqual(len(normalize_bars([row], datetime(2027, 1, 5, 11, 0, tzinfo=msk))), 1)

    def test_daily_candle_is_not_complete_during_its_trading_day(self):
        row = {"begin": "2027-01-05 00:00:00", "end": "2027-01-05 12:00:00",
               "open": 100, "high": 102, "low": 99, "close": 101}
        msk = ZoneInfo("Europe/Moscow")
        self.assertEqual(normalize_bars([row], datetime(2027, 1, 5, 23, tzinfo=msk), interval=24), [])
        self.assertEqual(len(normalize_bars([row], datetime(2027, 1, 6, 0, tzinfo=msk), interval=24)), 1)

    def test_timeout_is_data_unavailable_and_never_an_order(self):
        with patch("service.data_sources.moex.time.sleep"):
            with patch("service.data_sources.moex.urllib.request.urlopen", side_effect=TimeoutError("timed out")):
                with self.assertRaises(MarketDataUnavailable) as raised:
                    fetch_candles("PLZL", "2027-01-01", self.now)
        report = poll_error("DATA_UNAVAILABLE", raised.exception, self.now, 900)
        self.assertEqual(report["orders_created"], 0)
        self.assertEqual(report["retry_after_seconds"], 900)

    def test_cache_refreshes_recent_day_and_failure_does_not_trade_from_stale_data(self):
        def response(rows):
            payload = {"candles": {"columns": ["begin", "close"], "data": rows}}
            return io.BytesIO(json.dumps(payload).encode())

        with TemporaryDirectory() as tmp:
            cache = Path(tmp) / "PLZL.json"
            with patch("service.data_sources.moex.urllib.request.urlopen", side_effect=[
                    response([["2027-01-01 09:00:00", 100], ["2027-01-02 10:00:00", 101]]),
                    response([["2027-01-02 10:00:00", 101], ["2027-01-03 11:00:00", 102]])]) as request:
                first = fetch_candles("PLZL", "2027-01-01", self.now, cache)
                second = fetch_candles("PLZL", "2027-01-01", self.now, cache)
            self.assertEqual(len(first), 2)
            self.assertEqual(len(second), 3)
            self.assertIn("from=2027-01-02", request.call_args_list[1].args[0])
            before = cache.read_bytes()
            with patch("service.data_sources.moex.time.sleep"):
                with patch("service.data_sources.moex.urllib.request.urlopen", side_effect=TimeoutError("timed out")):
                    with self.assertRaises(MarketDataUnavailable):
                        fetch_candles("PLZL", "2027-01-01", self.now, cache)
            self.assertEqual(cache.read_bytes(), before)

    def test_candle_request_reports_url_duration_and_rows(self):
        payload = {"candles": {"columns": ["begin", "close"],
                               "data": [["2027-01-01 09:00:00", 100]]}}
        recorded = []
        with patch("service.data_sources.moex.urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(payload).encode())):
            fetch_candles("PLZL", "2027-01-01", self.now, request_log=recorded.append)
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["symbol"], "PLZL")
        self.assertEqual(recorded[0]["rows"], 1)
        self.assertIn("interval=60", recorded[0]["url"])

    def test_daily_request_uses_daily_interval(self):
        payload = {"candles": {"columns": ["begin", "close"],
                               "data": [["2027-01-05 00:00:00", 100]]}}
        recorded = []
        with patch("service.data_sources.moex.urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(payload).encode())):
            rows = fetch_candles("SMLT", "2027-01-01", datetime(2027, 1, 6, 0, tzinfo=ZoneInfo("Europe/Moscow")),
                                 interval=24, request_log=recorded.append)
        self.assertEqual(len(rows), 1)
        self.assertIn("interval=24", recorded[0]["url"])


if __name__ == "__main__":
    unittest.main()
