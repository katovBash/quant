"""The dashboard must read paper state without treating a pending order as a position."""

import json
from io import BytesIO
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from workers.discovery.control import status as discovery_status
from web.server import (Handler, experiment_report_path, experiment_rows, pine_path,
                        recent_json_lines, render_page, snapshot)


class DashboardTests(unittest.TestCase):
    def test_experiment_list_uses_current_decisions_and_excludes_activated_paper(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "experiments"
            folder.mkdir()
            ids = ("alpha/pending", "alpha/closed", "alpha/active")
            (folder / "PACKAGE_STATUS.json").write_text(json.dumps({"experiments": [
                {"experiment": "experiments/" + item, "status": "REVIEW_ONLY"} for item in ids]}))
            for item in ids:
                results = folder / item / "results"
                results.mkdir(parents=True)
                (results / "REPORT.md").write_text("# Report " + item)
            (folder / "alpha/closed/results/decision.json").write_text(json.dumps({
                "status": "CLOSED", "reason": "Доходность ниже порога", "decided_by": "trader"}))
            (folder / "alpha/active/results/paper_review.json").write_text(json.dumps({
                "activation": {"accounts": 1}}))
            rows = experiment_rows(root)
            self.assertEqual([(row["id"], row["review_state"]) for row in rows],
                             [("alpha/pending", "pending"), ("alpha/closed", "closed")])
            self.assertEqual(rows[1]["reason"], "Доходность ниже порога")
            self.assertEqual(experiment_report_path(root, "alpha/closed", "final"),
                             (folder / "alpha/closed/results/REPORT.md").resolve())
            self.assertIsNone(experiment_report_path(root, "alpha/active", "final"))
            self.assertIsNone(experiment_report_path(root, "../alpha/closed", "final"))

    def test_pine_api_serves_only_catalogued_strategy_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategies = root / "strategies"
            script = strategies / "test-rule" / "strategy.pine"
            script.parent.mkdir(parents=True)
            script.write_text("//@version=6\nstrategy(\"Test\")\n", encoding="utf-8")
            catalog = strategies / "catalog.json"
            catalog.write_text(json.dumps({"rules": [{"id": "test-rule"}]}))
            handler = object.__new__(Handler)
            handler.path = "/api/strategies/test-rule/pine"
            handler.wfile = BytesIO()
            responses = []
            handler.send_response = responses.append
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            with patch("web.server.CATALOG", catalog), patch("web.server.STRATEGIES", strategies):
                self.assertEqual(pine_path("test-rule"), script.resolve())
                self.assertIsNone(pine_path("../test-rule"))
                handler.do_GET()
                self.assertIsNone(pine_path("unknown-rule"))
            self.assertEqual(responses, [200])
            self.assertIn(b'//@version=6', handler.wfile.getvalue())

    def test_discovery_switch_uses_persistent_cli_state(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            handler = object.__new__(Handler)
            handler.path = "/api/discovery"
            handler.server = SimpleNamespace(server_port=8765)
            handler.headers = {"Origin": "http://127.0.0.1:8765", "Content-Length": "16"}
            handler.rfile = BytesIO(b'{"enabled":true}')
            handler.wfile = BytesIO()
            responses = []
            handler.send_response = responses.append
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            with patch("web.server.ROOT", root):
                handler.do_POST()
            self.assertEqual(responses, [200])
            self.assertTrue(discovery_status(root)["enabled"])
            self.assertTrue(json.loads(handler.wfile.getvalue())["enabled"])

    def test_discovery_switch_rejects_foreign_origin(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            handler = object.__new__(Handler)
            handler.path = "/api/discovery"
            handler.server = SimpleNamespace(server_port=8765)
            handler.headers = {"Origin": "https://other.example", "Content-Length": "16"}
            handler.rfile = BytesIO(b'{"enabled":true}')
            errors = []
            handler.send_error = lambda *args: errors.append(args)
            with patch("web.server.ROOT", root):
                handler.do_POST()
            self.assertEqual(errors[0][0], 403)
            self.assertFalse(discovery_status(root)["enabled"])

    def test_improvement_endpoint_routes_only_same_origin_strategy_start(self):
        handler = object.__new__(Handler)
        handler.path = "/api/improvements"
        handler.server = SimpleNamespace(server_port=8765)
        body = b'{"action":"start","strategy_id":"test-rule"}'
        handler.headers = {"Origin": "http://127.0.0.1:8765", "Content-Length": str(len(body))}
        handler.rfile = BytesIO(body)
        handler.wfile = BytesIO()
        responses = []
        handler.send_response = responses.append
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        with patch("web.server.start_improvement", return_value={"stage": "PLANNING"}) as start:
            handler.do_POST()
        self.assertEqual(responses, [200])
        start.assert_called_once()
        self.assertEqual(json.loads(handler.wfile.getvalue())["stage"], "PLANNING")

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
        self.assertIn("if(location.protocol==='file:')location.replace('http://127.0.0.1:8765/'+location.hash)", html)
        self.assertNotIn('НЕ ПРОХОДИТ ОТБОР', html)
        self.assertIn('2М: можно оценить', html)
        self.assertIn('id="detail"', html)
        self.assertIn('id="history-after"', html)
        self.assertIn('id="history-before"', html)
        self.assertIn('id="discovery-toggle"', html)
        self.assertIn('id="improve-start"', html)
        self.assertIn('id="improve-guidance"', html)
        self.assertIn('/api/improvements', html)
        self.assertIn('id="pine-open"', html)
        self.assertIn('id="pine-dialog"', html)
        self.assertIn('id="pine-copy"', html)
        self.assertIn('id="experiment-list"', html)
        self.assertIn('id="experiment-search"', html)
        self.assertIn('id="experiment-dialog"', html)
        self.assertIn('/api/experiments/', html)
        self.assertIn('/api/discovery', html)
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
            self.assertIn("enabled", result["discovery"])

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

    def test_snapshot_includes_every_recovered_event_with_trade_bar_date(self):
        with TemporaryDirectory() as tmp:
            live = Path(tmp)
            account = live / "TEST-1D"
            account.mkdir()
            (live / "fleet_status.json").write_text(json.dumps({"accounts": [
                {"account_id": "TEST-1D", "status": "OK"}]}))
            (account / "state.json").write_text(json.dumps({
                "initial_capital": 1000000, "position": 1, "equity_log": [],
                "trades_log": [
                    {"action": "GAP", "observed_at": "2026-11-07T08:00:00+03:00",
                     "fill_bar": "2026-11-06 10:00:00"},
                    {"action": "OPEN_LONG", "observed_at": "2026-11-07T08:00:00+03:00",
                     "fill_bar": "2026-11-06 18:00:00", "recovered_after_gap": True}]}))
            events = snapshot(live)["events"]
            self.assertEqual([event["action"] for event in events], ["OPEN_LONG", "GAP"])
            self.assertEqual(events[0]["fill_bar"][:10], "2026-11-06")
            self.assertEqual(events[0]["observed_at"][:10], "2026-11-07")


if __name__ == "__main__":
    unittest.main()
