"""Corporate-event data must be traceable and applied on observed candles only."""

import csv
import unittest
from pathlib import Path

from src.research.corporate_actions import dividends_for, load_dividend_snapshot
from src.research.timeframes import load_research_bars

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data/dividends/sfin_2026-11-04.json"


class CorporateActionsTests(unittest.TestCase):
    def test_sfin_dividend_snapshot_has_sources_and_trade_dates(self):
        snapshot, digest = load_dividend_snapshot(SNAPSHOT)
        self.assertEqual(len(digest), 64)
        self.assertEqual(len(snapshot["events"]), 5)
        for timeframe in ("1H", "4H", "1D"):
            with self.subTest(timeframe=timeframe):
                bars = load_research_bars(ROOT / "data/candles/moex_scan", "SFIN", timeframe)
                payouts = dividends_for(snapshot, "SFIN", bars)
                self.assertEqual(len(payouts), 5)
                self.assertEqual(payouts["2025-12-25"], 902.0)

    def test_missing_event_candle_is_rejected(self):
        snapshot, _ = load_dividend_snapshot(SNAPSHOT)
        with self.assertRaisesRegex(ValueError, "missing effective trading candle"):
            dividends_for(snapshot, "SFIN", [{"ts": "2025-12-24 10:00:00"},
                                              {"ts": "2025-12-26 10:00:00"}])

    def test_unverified_symbol_cannot_be_assumed_dividend_free(self):
        snapshot, _ = load_dividend_snapshot(SNAPSHOT)
        with self.assertRaisesRegex(ValueError, "coverage not verified"):
            dividends_for(snapshot, "SBER", [{"ts": "2026-11-04 10:00:00"}])

    def test_original_turtle_result_reproduced_before_adjustment(self):
        from importlib import util

        path = ROOT / "experiments/turtle/period-grid/run.py"
        spec = util.spec_from_file_location("turtle_grid", path)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bars = load_research_bars(ROOT / "data/candles/moex_scan", "SFIN", "1H")
        actual = next(row for row in module.evaluate("SFIN", "1H", bars)[0]
                      if row["variant"] == "dennis_turtle_55_20")
        with (ROOT / "experiments/turtle/period-grid/results/all_variants.csv").open() as stream:
            recorded = next(row for row in csv.DictReader(stream)
                            if row["symbol"] == "SFIN" and row["timeframe"] == "1H"
                            and row["variant"] == "dennis_turtle_55_20")
        self.assertAlmostEqual(actual["pnl_rub"], float(recorded["pnl_rub"]))


if __name__ == "__main__":
    unittest.main()
