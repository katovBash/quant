import csv
import tempfile
import unittest
from pathlib import Path

from src.research.experiment_report import build_report


class ExperimentReportTests(unittest.TestCase):
    def test_monthly_metrics_and_optional_control(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            rows = [
                {"symbol": "AAA", "timeframe": "4H", "variant": "baseline",
                 "pnl_rub": 0, "net_return_pct": 0, "positive_months": 1,
                 "worst_month_pnl_rub": -100},
                {"symbol": "AAA", "timeframe": "4H", "variant": "retest",
                 "pnl_rub": 200, "net_return_pct": 0.02, "positive_months": 1,
                 "worst_month_pnl_rub": -50},
            ]
            monthly = []
            for variant, pnls in (("baseline", [-100, 100]), ("retest", [-50, 250])):
                for index, pnl in enumerate(pnls, 1):
                    monthly.append({"symbol": "AAA", "timeframe": "4H", "variant": variant,
                                    "start": f"2026-0{index}-01", "pnl_rub": pnl,
                                    "return_pct": pnl / 10000, "closed_trades": 1,
                                    "sample": "train" if index == 1 else "late"})
            build_report(output, {"signal_timeframes": ["4H"],
                                  "primary_evaluation": "monthly"},
                         {"cost_model": "gross_before_costs", "errors": []}, rows, monthly)
            with (output / "monthly_case_summary.csv").open(encoding="utf-8") as stream:
                cases = {item["variant"]: item for item in csv.DictReader(stream)}
            self.assertEqual(cases["retest"]["profitable_months"], "1")
            self.assertEqual(cases["retest"]["losing_months"], "1")
            self.assertEqual(float(cases["retest"]["mean_month_pnl_rub"]), 100)
            self.assertEqual(float(cases["retest"]["mean_profitable_month_pnl_rub"]), 250)
            self.assertEqual(cases["retest"]["worst_month_pnl_rub"], "-50.0")
            self.assertIn("gross_before_costs", (output / "REPORT.md").read_text())

            build_report(output, {"signal_timeframes": ["4H"]}, {}, rows[1:], monthly[2:])
            self.assertIn("Сопоставимых вариантов с контролем нет",
                          (output / "REPORT.md").read_text())


if __name__ == "__main__":
    unittest.main()
