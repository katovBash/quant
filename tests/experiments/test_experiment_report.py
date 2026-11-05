import csv
import tempfile
import unittest
from pathlib import Path

from src.research.experiment_report import build_report
from src.research.annual_returns import calendar_years


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
                equity = 1_000_000
                for index, pnl in enumerate(pnls, 1):
                    monthly.append({"symbol": "AAA", "timeframe": "4H", "variant": variant,
                                    "start": f"2026-0{index}-01", "pnl_rub": pnl,
                                    "starting_equity_rub": equity,
                                    "ending_equity_rub": equity + pnl,
                                    "return_pct": pnl / 10000, "closed_trades": 1,
                                    "sample": "train" if index == 1 else "late"})
                    equity += pnl
            with (output / "trade_side_summary.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=(
                    "symbol", "timeframe", "variant", "mode", "long_closed", "long_wins",
                    "short_closed", "short_wins", "return_pct", "profitable_months",
                    "months", "conclusion"))
                writer.writeheader()
                writer.writerow({"symbol": "AAA", "timeframe": "4H", "variant": "retest",
                                 "mode": "long_only", "long_closed": 4, "long_wins": 3,
                                 "short_closed": 0, "short_wins": 0, "return_pct": 2.5,
                                 "profitable_months": 2, "months": 3,
                                 "conclusion": "К следующей проверке: long_only"})
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
            self.assertEqual(float(cases["retest"]["last_1m_mean_month_pnl_rub"]), 250)
            self.assertEqual(cases["retest"]["last_3m_mean_month_pnl_rub"], "")
            self.assertEqual(cases["retest"]["last_9m_mean_month_pnl_rub"], "")
            self.assertIn("Последние 9 месяцев", (output / "REPORT.md").read_text())
            self.assertIn("gross_before_costs", (output / "REPORT.md").read_text())
            self.assertIn("Последние 12 месяцев", (output / "REPORT.md").read_text())
            report = (output / "REPORT.md").read_text()
            self.assertIn("## Каждый полный месяц", report)
            self.assertIn("## PnL по календарным годам", report)
            self.assertIn("2026 · 01–02 (неполный)", report)
            self.assertNotIn("| Весь период |", report)
            self.assertIn("🟥 -0.01%", report)
            self.assertIn("🟩 +0.03%", report)
            self.assertIn("## Long и short по отдельности", report)
            self.assertIn("3/4 · 75.0%", report)
            self.assertIn("К следующей проверке: long_only", report)

            build_report(output, {"signal_timeframes": ["4H"]}, {}, rows[1:], monthly[2:])
            self.assertIn("Сопоставимых вариантов с контролем нет",
                          (output / "REPORT.md").read_text())


if __name__ == "__main__":
    unittest.main()


class AnnualReturnsTests(unittest.TestCase):
    def test_calendar_year_uses_continuous_equity_and_marks_partial_year(self):
        months = [
            {"start": "2024-01-01", "starting_equity_rub": "1000000", "ending_equity_rub": "1100000"},
            {"start": "2024-02-01", "starting_equity_rub": "1100000", "ending_equity_rub": "1210000"},
            {"start": "2025-01-01", "starting_equity_rub": "1210000", "ending_equity_rub": "1089000"},
        ]
        years = calendar_years(months)
        self.assertEqual(years[0]["pnl_rub"], 210000)
        self.assertEqual(years[0]["return_pct"], 21)
        self.assertFalse(years[0]["complete"])
        self.assertEqual(years[1]["return_pct"], -10)
