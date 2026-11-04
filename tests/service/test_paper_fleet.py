"""The fleet must isolate virtual accounts and wait for completed 4H groups."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from papertrading.setup import load_setup
from service.data_sources.moex import HTTP_BASE, MOSCOW, normalize_bars
from service.paper_fleet import accounts, discover_new_setups, poll
from service.paper_runner import completed_four_hour, load_strategy
from src.research.timeframes import source_path


class PaperFleetTests(unittest.TestCase):
    def test_complete_new_strategy_gets_frozen_account_once(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            setups = root / "setups"
            setups.mkdir()
            strategy = root / "strategies" / "example-1h"
            strategy.mkdir(parents=True)
            (strategy / "README.md").write_text("# Example\n")
            (strategy / "strategy.pine").write_text("//@version=6\n")
            (strategy / "strategy.py").write_text(
                "STRATEGY_ID = 'example-1h'\nSYMBOL = 'TEST'\nTIMEFRAME = '1H'\n"
                "def signal(bars): return 0\n")
            universe = root / "universe.json"
            universe.write_text(json.dumps([{"SECID": "TEST", "LOTSIZE": 10}]))
            created = discover_new_setups(setups, root / "strategies", universe)
            self.assertEqual(len(created), 1)
            self.assertEqual(load_setup(created[0])["lot_size_shares"], 10)
            self.assertEqual(load_setup(created[0])["position_weight_pct"], 10)
            self.assertEqual(discover_new_setups(setups, root / "strategies", universe), [])

    def test_ranked_rule_uses_fixed_top_stocks_without_symbol_in_name(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            setups = root / "setups"
            setups.mkdir()
            strategy = root / "strategies" / "ema-example-1h"
            strategy.mkdir(parents=True)
            (strategy / "README.md").write_text("# EMA rule\n")
            (strategy / "strategy.pine").write_text("//@version=6\n")
            (strategy / "strategy.py").write_text(
                "STRATEGY_ID = 'ema-example-1h'\nTIMEFRAME = '1H'\n"
                "def signal(bars): return 0\n")
            (strategy / "selection.json").write_text(json.dumps({
                "id": "ema-example-1h", "timeframe": "1H",
                "status": "HISTORICAL_RANKING",
                "top10": [{"symbol": "AAA"}, {"symbol": "BBB"}]}))
            universe = root / "universe.json"
            universe.write_text(json.dumps([{"SECID": "AAA", "LOTSIZE": 10},
                                            {"SECID": "BBB", "LOTSIZE": 1}]))
            created = discover_new_setups(setups, root / "strategies", universe)
            self.assertEqual(len(created), 2)
            self.assertEqual({load_setup(path)["symbol"] for path in created}, {"AAA", "BBB"})
            self.assertEqual(discover_new_setups(setups, root / "strategies", universe), [])

    def test_daily_ranked_rule_gets_a_setup(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            setups = root / "setups"
            setups.mkdir()
            strategy = root / "strategies" / "ema-daily"
            strategy.mkdir(parents=True)
            (strategy / "README.md").write_text("# EMA daily\n")
            (strategy / "strategy.pine").write_text("//@version=6\n")
            (strategy / "strategy.py").write_text(
                "STRATEGY_ID = 'ema-daily'\nTIMEFRAME = '1D'\n"
                "def signal(bars): return 0\n")
            (strategy / "selection.json").write_text(json.dumps({
                "id": "ema-daily", "timeframe": "1D", "status": "HISTORICAL_RANKING",
                "top10": [{"symbol": "TEST"}]}))
            universe = root / "universe.json"
            universe.write_text(json.dumps([{"SECID": "TEST", "LOTSIZE": 10}]))
            created = discover_new_setups(setups, root / "strategies", universe)
            self.assertEqual(len(created), 1)
            self.assertEqual(load_setup(created[0])["timeframe"], "1D")
            with patch("service.paper_fleet.load_strategy", return_value=SimpleNamespace(TIMEFRAME="1D")):
                self.assertEqual(accounts(setups, root / "live")[0].history_from, "2022-01-01")

    def test_every_configured_rule_is_registered_and_accounts_are_unique(self):
        configs = accounts(Path("papertrading/setups/fleet"), Path("/tmp/unused-paper-test"))
        self.assertEqual(len(configs), len(list(Path("papertrading/setups/fleet").glob("*.json"))))
        self.assertEqual(len({item.account_id for item in configs}), len(configs))
        self.assertGreaterEqual(len({item.symbol for item in configs}), 8)
        for item in configs:
            self.assertEqual(load_strategy(item.strategy_id).STRATEGY_ID, item.strategy_id)

    def test_four_hour_waits_for_full_current_group_and_keeps_previous_end(self):
        start = datetime(2027, 1, 4, 10, tzinfo=MOSCOW)
        rows = []
        for day, hours in ((0, 6), (1, 1)):
            for hour in range(hours):
                stamp = start + timedelta(days=day, hours=hour)
                rows.append({"begin": stamp.strftime("%Y-%m-%d %H:%M:%S"),
                             "open": 100, "high": 101, "low": 99, "close": 100, "volume": 1})
        now = start + timedelta(days=1, hours=2)
        bars = normalize_bars(rows, now)
        grouped = completed_four_hour(bars, now)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(grouped[-1]["end"], bars[5]["end"])

    def test_seeding_uses_one_fetch_per_ticker_and_creates_no_old_orders(self):
        with TemporaryDirectory() as tmp:
            configs = accounts(Path("papertrading/setups/fleet"), Path(tmp))
            now = datetime(2026, 11, 1, 18, tzinfo=MOSCOW)

            def saved_candles(symbol, history_from, now, cache_path, require_ohlc, interval):
                self.assertTrue(require_ohlc)
                path = source_path(Path("data/moex_scan"), symbol, "1D" if interval == 24 else "1H")
                return normalize_bars(json.loads(path.read_text()), now, interval=interval)

            with patch("service.paper_fleet.fetch_candles", side_effect=saved_candles) as fetch:
                rows = poll(configs, now, preflight=False)
            self.assertEqual(fetch.call_count, len({(item.symbol, item.timeframe == "1D") for item in configs}))
            self.assertEqual(len(rows), len(configs))
            self.assertTrue(all(row["status"] == "OK" and row["orders_created"] == 0 for row in rows))
            self.assertEqual(len(list(Path(tmp).glob("*/state.json"))), len(configs))

    def test_source_outage_skips_candles_and_creates_no_orders(self):
        with TemporaryDirectory() as tmp:
            configs = accounts(Path("papertrading/setups/fleet"), Path(tmp))
            now = datetime(2026, 11, 1, 18, tzinfo=MOSCOW)
            with patch("service.paper_fleet.urllib.request.urlopen", side_effect=TimeoutError("offline")):
                with patch("service.paper_fleet.fetch_candles") as fetch:
                    rows = poll(configs, now)
            fetch.assert_not_called()
            self.assertEqual(len(rows), len(configs))
            self.assertTrue(all(row["status"] == "DATA_UNAVAILABLE" and row["orders_created"] == 0 for row in rows))
            self.assertEqual(list(Path(tmp).glob("*/state.json")), [])

    def test_https_timeout_uses_http_only_for_paper_candles(self):
        now = datetime(2026, 11, 2, 12, tzinfo=MOSCOW)
        config = accounts(Path("papertrading/setups/fleet"), Path("/tmp/unused-paper-test"))[0]
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch("service.paper_fleet.urllib.request.urlopen",
                   side_effect=[TimeoutError("https unavailable"), response]) as preflight:
            with patch("service.paper_fleet.fetch_candles", return_value=[]) as fetch:
                with patch("service.paper_fleet.run_once", return_value={"status": "OK"}):
                    rows = poll([config], now)
        self.assertEqual(preflight.call_count, 2)
        self.assertEqual(fetch.call_args.kwargs["base_url"], HTTP_BASE)
        self.assertEqual(rows[0]["source"], "MOEX ISS HTTP (unencrypted)")

    def test_preflight_requests_are_logged_with_result(self):
        with TemporaryDirectory() as tmp:
            now = datetime(2026, 11, 2, 12, tzinfo=MOSCOW)
            config = accounts(Path("papertrading/setups/fleet"), Path(tmp))[0]
            response = MagicMock()
            response.__enter__.return_value.status = 200
            log = Path(tmp) / "fleet_requests.ndjson"
            with patch("service.paper_fleet.urllib.request.urlopen", return_value=response):
                with patch("service.paper_fleet.fetch_candles", return_value=[]):
                    with patch("service.paper_fleet.run_once", return_value={"status": "OK"}):
                        poll([config], now, request_log=log)
            entry = json.loads(log.read_text().splitlines()[0])
            self.assertEqual((entry["kind"], entry["status"], entry["http_status"]),
                             ("preflight", "OK", 200))


if __name__ == "__main__":
    unittest.main()
