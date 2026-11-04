import csv
import json
import tempfile
import unittest
from pathlib import Path

from criteria.promote_experiment import promote


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.experiment = self.root / "experiments/ema-example"
        self.experiment.mkdir(parents=True)
        (self.root / "strategies").mkdir()
        (self.experiment / "strategy.pine").write_text("//@version=6\n", encoding="utf-8")
        (self.experiment / "strategy.py").write_text("def target_side(*args):\n    return None\n", encoding="utf-8")
        with (self.experiment / "results.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=("symbol", "timeframe", "fast", "slow", "mode",
                "closed_trades", "oos_trades", "net_return_pct", "oos_return_pct",
                "profit_factor", "max_drawdown_pct"))
            writer.writeheader()
            writer.writerow(dict(symbol="PLZL", timeframe="1H", fast=12, slow=33,
                mode="long_short", closed_trades=120, oos_trades=40,
                net_return_pct=15, oos_return_pct=5, profit_factor=1.5,
                max_drawdown_pct=12))
        (self.experiment / "monthly.json").write_text(json.dumps({"pairs": [{
            "symbol": "PLZL", "timeframe": "1H",
            "monthly_start_windows": {"1": {"count": 12, "negative_count": 0,
                                                   "worst": {"return_pct": 0.1},
                                                   "all": [{"start": f"2024-{month:02d}-01",
                                                            "return_pct": 0.1,
                                                            "pnl_rub": 1000,
                                                            "closed_trades": 10,
                                                            "winning_trades": 3}
                                                           for month in range(1, 13)]}}}]}),
            encoding="utf-8")
        with (self.experiment / "trade_windows_100.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=("symbol", "timeframe", "first_trade_number",
                "last_trade_number", "closed_trades", "winning_trades", "pnl_rub"))
            writer.writeheader()
            writer.writerow(dict(symbol="PLZL", timeframe="1H", first_trade_number=1,
                last_trade_number=100, closed_trades=100, winning_trades=30, pnl_rub=5000))
        self.spec = dict(slug="ema-example", scope="basket", symbols=["PLZL", "VTBR"],
            source_csv="results.csv", monthly_report="monthly.json",
            trade_window_report="trade_windows_100.csv",
            selector=dict(symbol="PLZL", timeframe="1H", fast="12", slow="33", mode="long_short"),
            pine="strategy.pine", python="strategy.py", rule="EMA12/33, long+short", frozen_on="2026-11-01",
            review=dict(no_lookahead_checked=True, stable_neighbors_checked=True,
                control_checked=True, costs_checked=True, cross_ticker_checked=True,
                notes="Проверено вручную."))
        self.save()

    def save(self):
        (self.experiment / "candidate.json").write_text(json.dumps(self.spec), encoding="utf-8")

    def test_dry_run_does_not_copy_and_apply_copies_only_code(self):
        self.assertFalse(promote(self.experiment, self.root)["applied"])
        destination = self.root / "strategies/ema-example"
        self.assertFalse(destination.exists())
        promote(self.experiment, self.root, apply=True)
        self.assertEqual({p.name for p in destination.iterdir()}, {"README.md", "strategy.pine", "strategy.py", "robustness.json"})
        self.assertTrue((self.experiment / "results.csv").exists())

    def test_review_and_historical_gate_both_required(self):
        self.spec["review"]["control_checked"] = False
        self.save()
        with self.assertRaisesRegex(ValueError, "review flags"):
            promote(self.experiment, self.root)
        self.spec["review"]["control_checked"] = True
        self.save()
        path = self.experiment / "results.csv"
        contents = path.read_text().replace(",120,40,15,5,", ",10,4,-15,5,")
        path.write_text(contents)
        with self.assertRaisesRegex(ValueError, "historical screen failed"):
            promote(self.experiment, self.root)

    def test_tv_review_allows_pending_costs_and_copies_python_signal(self):
        self.spec["review_stage"] = "tv_review"
        self.spec["review"]["costs_checked"] = False
        self.save()
        result = promote(self.experiment, self.root, apply=True)
        self.assertEqual(result["status"], "TV_REVIEW")
        self.assertIn("Ожидает ручной сверки", (self.root / "strategies/ema-example/README.md").read_text())
        self.assertTrue((self.root / "strategies/ema-example/strategy.py").exists())

    def test_candidate_requires_both_implementations(self):
        self.spec.pop("python")
        self.save()
        with self.assertRaisesRegex(ValueError, "requires both"):
            promote(self.experiment, self.root)

    def test_monthly_loss_is_recorded_but_does_not_block_candidate(self):
        path = self.experiment / "monthly.json"
        report = json.loads(path.read_text())
        report["pairs"][0]["monthly_start_windows"]["1"]["negative_count"] = 1
        report["pairs"][0]["monthly_start_windows"]["1"]["all"][0]["return_pct"] = -0.1
        path.write_text(json.dumps(report))
        self.assertEqual(promote(self.experiment, self.root)["status"], "HISTORICAL_CANDIDATE")

    def test_two_distinct_months_required_for_monthly_review(self):
        path = self.experiment / "monthly.json"
        report = json.loads(path.read_text())
        windows = report["pairs"][0]["monthly_start_windows"]["1"]
        windows["all"] = windows["all"][:2]
        windows["count"] = 2
        path.write_text(json.dumps(report))
        self.assertEqual(promote(self.experiment, self.root)["status"], "HISTORICAL_CANDIDATE")
        windows["all"] = windows["all"][:1]
        windows["count"] = 1
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "distinct months"):
            promote(self.experiment, self.root)

    def test_monthly_report_is_required(self):
        self.spec.pop("monthly_report")
        self.save()
        with self.assertRaises(KeyError):
            promote(self.experiment, self.root)

    def test_missing_100_trade_window_does_not_block_monthly_candidate(self):
        path = self.experiment / "trade_windows_100.csv"
        path.write_text("symbol,timeframe,first_trade_number,last_trade_number,closed_trades,winning_trades,pnl_rub\n")
        self.assertEqual(promote(self.experiment, self.root)["status"], "HISTORICAL_CANDIDATE")

    def test_single_ticker_does_not_require_cross_ticker_profit(self):
        self.spec["scope"] = "single_ticker"
        self.spec["symbols"] = ["PLZL"]
        self.spec["review"]["cross_ticker_checked"] = False
        self.save()
        self.assertEqual(promote(self.experiment, self.root)["status"], "HISTORICAL_CANDIDATE")


if __name__ == "__main__":
    unittest.main()
