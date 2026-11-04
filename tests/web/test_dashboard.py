"""The dashboard must read paper state without treating a pending order as a position."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from web.server import recent_json_lines, render_page, snapshot


class DashboardTests(unittest.TestCase):
    def test_request_log_reads_latest_entries(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "requests.ndjson"
            path.write_text("".join(json.dumps({"n": n}) + "\n" for n in range(5)))
            self.assertEqual([row["n"] for row in recent_json_lines(path, 2)], [4, 3])

    def test_html_contains_embedded_snapshot_without_remote_fetch(self):
        html = render_page({"accounts": [{"account_id": "TEST"}], "error": "</script>"}).decode()
        self.assertIn("TEST", html)
        self.assertIn("\\u003c/script>", html)
        self.assertNotIn("__INITIAL_SNAPSHOT__", html)
        self.assertIn('id="strategy-grid"', html)
        self.assertIn('id="detail"', html)
        self.assertIn("История: доходность", html)
        self.assertIn("PnL", html)
        self.assertNotIn("Медиана истории", html)

    def test_source_outage_keeps_last_known_account_identity_and_position(self):
        with TemporaryDirectory() as tmp:
            live = Path(tmp)
            account = live / "TEST-1H"
            account.mkdir()
            (live / "fleet_status.json").write_text(json.dumps({
                "observed_at": "2026-11-02T09:00:00+03:00",
                "accounts": [{"account_id": "TEST-1H", "status": "DATA_UNAVAILABLE",
                              "error": "timeout"}]
            }))
            (account / "state.json").write_text(json.dumps({
                "symbol": "TEST", "strategy": "rule", "timeframe": "1H",
                "initial_capital": 1000000, "position": -10, "closed_trades": 2,
                "equity_log": [], "trades_log": []
            }))
            row = snapshot(live)["accounts"][0]
            self.assertEqual((row["symbol"], row["strategy"], row["side"]),
                             ("TEST", "rule", "SHORT"))
            self.assertTrue(snapshot(live)["shared_source_error"])

    def test_snapshot_distinguishes_open_position_from_pending_signal(self):
        with TemporaryDirectory() as tmp:
            live = Path(tmp)
            account = live / "TEST-1H"
            account.mkdir()
            (live / "fleet_status.json").write_text(json.dumps({
                "observed_at": "2026-11-02T09:00:00+03:00",
                "accounts": [{"account_id": "TEST-1H", "symbol": "TEST", "strategy": "rule",
                              "timeframe": "1H", "status": "OK", "pending": {"side": "short"}}]
            }))
            (account / "state.json").write_text(json.dumps({
                "initial_capital": 1000000, "position": 0, "closed_trades": 0,
                "started_at": "2026-11-01T09:00:00+03:00",
                "equity_log": [], "trades_log": []
            }))
            result = snapshot(live, datetime(2026, 11, 2, 6, 5, tzinfo=timezone.utc))
            self.assertEqual(result["accounts"][0]["side"], "FLAT")
            self.assertEqual(result["accounts"][0]["pending"]["side"], "short")
            self.assertEqual(result["accounts"][0]["return_pct"], 0)
            self.assertEqual(result["accounts"][0]["started_at"], "2026-11-01T09:00:00+03:00")
            self.assertTrue(result["fresh"])
            self.assertFalse(result["fleet_running"])

    def test_strategy_list_contains_configured_stocks_before_first_poll(self):
        with TemporaryDirectory() as tmp:
            rules = snapshot(Path(tmp))["rules"]
            ema = next(row for row in rules if row["id"] == "ema-level-79-atr025-long-short-1h")
            self.assertIn("WUSH", ema["configured_symbols"])
            self.assertTrue(ema["top10"])

    def test_open_pnl_is_zero_when_flat_and_marks_long_or_short_positions(self):
        with TemporaryDirectory() as tmp:
            live = Path(tmp)
            rows = []
            for account_id, position, mark in (("LONG", 10, 110), ("SHORT", -10, 90), ("FLAT", 0, 100)):
                rows.append({"account_id": account_id, "symbol": account_id,
                             "strategy": "test", "timeframe": "1H", "status": "OK"})
                folder = live / account_id
                folder.mkdir()
                (folder / "state.json").write_text(json.dumps({
                    "initial_capital": 1000000, "position": position, "entry_flow": 1000,
                    "equity_log": [{"strategy_equity": 1000000, "mark_price": mark}],
                    "trades_log": []}))
            (live / "fleet_status.json").write_text(json.dumps({"accounts": rows}))
            actual = {row["account_id"]: row["open_pnl_rub"] for row in snapshot(live)["accounts"]}
            self.assertEqual(actual, {"LONG": 100, "SHORT": 100, "FLAT": 0})


if __name__ == "__main__":
    unittest.main()
