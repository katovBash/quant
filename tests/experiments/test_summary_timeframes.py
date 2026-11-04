"""Coverage in summaries must never invent 15M or 30M returns."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.research.summary_timeframes import coverage_block, update_summary


class SummaryTimeframeTests(unittest.TestCase):
    def test_coverage_reports_only_existing_results(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / "rsi-grid-search"
            (folder / "results" / "1H").mkdir(parents=True)
            (folder / "results" / "1H" / "PLZL.csv").write_text("symbol,net_return_pct\nPLZL,1\n")
            (folder / "results" / "progress.csv").write_text(
                "symbol,timeframe,status,rows,detail\n"
                "PLZL,1H,complete,1,\n"
                "PLZL,15M,missing_cache,0,\n")
            content = coverage_block(folder)
            self.assertIn("| 1H | 1 | есть исторические результаты |", content)
            self.assertIn("| 15M | 0 | ожидает минутных свечей |", content)
            self.assertIn("| 30M | 0 | ожидает минутных свечей |", content)

    def test_update_is_idempotent(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "results").mkdir()
            (folder / "SUMMARY.md").write_text("# RSI\n\n## 1H\nExisting result\n")
            update_summary(folder)
            once = (folder / "SUMMARY.md").read_text()
            update_summary(folder)
            self.assertEqual(once, (folder / "SUMMARY.md").read_text())
            self.assertEqual(once.count("## Покрытие таймфреймов"), 1)

    def test_compressed_ema_results_count(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "results" / "4H").mkdir(parents=True)
            (folder / "results" / "4H" / "PLZL.csv.gz").write_bytes(b"placeholder")
            self.assertIn("| 4H | 1 | есть исторические результаты |", coverage_block(folder))


if __name__ == "__main__":
    unittest.main()
