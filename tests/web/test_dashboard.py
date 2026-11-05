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
        self.assertIn('id="history-after"', html)
        self.assertIn('id="history-before"', html)
        self.assertIn("1 месяц", html)
        self.assertIn("3 месяца", html)
        self.assertIn("6 месяцев", html)
        self.assertIn("9 месяцев", html)
        self.assertIn("доходность по месяцам", html)
        self.assertIn("12 месяцев", html)
        self.assertNotIn("Качество данных", html)
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
            turtle = next(row for row in rules if row["id"] == "dennis-turtle-55-20-1h")
            self.assertIn("SFIN", turtle["configured_symbols"])
            self.assertIn("WUSH", turtle["configured_symbols"])
            self.assertTrue(turtle["top10"])
            self.assertIn("after_costs_return_pct", turtle["top10"][0])
            self.assertEqual(turtle["top10"][0]["history"]["after"]["periods"]["1"]["return_pct"], -1.64)
            self.assertIsNotNone(turtle["top10"][0]["history"]["after"]["periods"]["9"])
            months = turtle["top10"][0]["history"]["after"]["months"]
            self.assertEqual(len(months), 33)
            self.assertEqual(months[-1]["month"], "2026-09")
            self.assertEqual(months[-1]["return_pct"], -1.64)
            self.assertEqual(turtle["top10"][0]["history"]["before"]["periods"]["12"]["return_pct"], 62.17)
            annual = turtle["top10"][0]["history"]["after"]["calendar_years"]
            self.assertEqual([item["year"] for item in annual], ["2024", "2025", "2026"])
            self.assertFalse(annual[-1]["complete"])
            self.assertEqual(turtle["data_quality"]["SFIN"]["dividends"], "verified_unapplied")
            self.assertEqual(turtle["data_quality"]["WUSH"]["splits"], "unverified")

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
