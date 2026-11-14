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
from service.paper_fleet import accounts, poll
from service.paper_runner import completed_four_hour, load_strategy
from src.research.timeframes import source_path


class PaperFleetTests(unittest.TestCase):
    def test_strategy_files_alone_do_not_create_a_paper_account(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            setups = root / "setups"
            setups.mkdir()
            strategy = root / "strategies" / "example-1h"
            strategy.mkdir(parents=True)
            (strategy / "strategy.pine").write_text("//@version=6\n")
            (strategy / "strategy.py").write_text(
                "STRATEGY_ID = 'example-1h'\nSYMBOL = 'TEST'\nTIMEFRAME = '1H'\n"
                "def signal(bars): return 0\n")
            self.assertEqual(list(setups.iterdir()), [])
            with self.assertRaisesRegex(ValueError, "no paper setups"):
                accounts(setups, root / "live")

    def test_fleet_reads_new_registered_setup_on_next_scan(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            setups = root / "setups"
            setups.mkdir()
            setup = {"account_id": "AAA-EXAMPLE-1H", "symbol": "AAA",
                     "strategy": "example-1h", "timeframe": "1H",
                     "initial_capital_rub": 1_000_000, "position_weight_pct": 10,
                     "mode": "long_short", "lot_size_shares": 10,
                     "fee_bps": 5, "slip_bps": 10,
                     "borrow_bps_annual": 0, "stop_loss_pct": None}
            with patch("service.paper_fleet.load_strategy",
                       return_value=SimpleNamespace(TIMEFRAME="1H")):
                with self.assertRaisesRegex(ValueError, "no paper setups"):
                    accounts(setups, root / "live")
                (setups / "approved.json").write_text(json.dumps(setup))
                self.assertEqual(accounts(setups, root / "live")[0].account_id,
                                 "AAA-EXAMPLE-1H")

    def test_daily_registered_rule_gets_daily_history(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            setups = root / "setups"
            setups.mkdir()
            setup = {"account_id": "TEST-EMA-DAILY", "symbol": "TEST",
                     "strategy": "ema-daily", "timeframe": "1D",
                     "initial_capital_rub": 1_000_000, "position_weight_pct": 10,
                     "mode": "long_short", "lot_size_shares": 10,
                     "fee_bps": 5, "slip_bps": 10,
                     "borrow_bps_annual": 0, "stop_loss_pct": None}
            (setups / "approved.json").write_text(json.dumps(setup))
            with patch("service.paper_fleet.load_strategy", return_value=SimpleNamespace(TIMEFRAME="1D")):
                self.assertEqual(accounts(setups, root / "live")[0].history_from, "2022-01-01")

    def test_every_configured_rule_is_registered_and_accounts_are_unique(self):
        configs = accounts(Path("papertrading/setups/fleet"), Path("/tmp/unused-paper-test"))
        self.assertEqual(len(configs), len(list(Path("papertrading/setups/fleet").glob("*.json"))))
        self.assertEqual(len({item.account_id for item in configs}), len(configs))
        self.assertGreaterEqual(len({item.symbol for item in configs}), 7)
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
                path = source_path(Path("data/candles/moex_scan"), symbol, "1D" if interval == 24 else "1H")
                return normalize_bars(json.loads(path.read_text()), now, interval=interval)

            with patch("service.paper_fleet.fetch_candles", side_effect=saved_candles) as fetch:
                rows = poll(configs, now, preflight=False)
            self.assertEqual(fetch.call_count, len({(item.symbol, item.timeframe in ("1D", "1W")) for item in configs}))
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
