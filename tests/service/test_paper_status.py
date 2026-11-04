"""The monthly paper label is derived from the recorded account, never a backtest."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from papertrading.status import publish


class PaperStatusTests(unittest.TestCase):
    def test_monthly_index_requires_cost_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            live = Path(tmp)
            account = live / "TEST"
            account.mkdir()
            state = {"symbol": "TEST", "strategy": "fixed-rule", "mode": "long_short",
                     "initial_capital": 1000, "started_at": "2026-01-01T10:00:00+03:00"}
            (account / "state.json").write_text(json.dumps(state), encoding="utf-8")
            with (account / "equity.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["date", "strategy_equity", "baseline_equity"])
                writer.writerow(["2026-01-02", "1000", "1000"])
                writer.writerow(["2026-01-31", "1010", "1000"])
            self.assertEqual(publish(live)[0]["paper_status"], "COSTS_UNVERIFIED")
            (account / "review.json").write_text(
                json.dumps({"costs_verified": True, "short_costs_verified": True}),
                encoding="utf-8",
            )
            result = publish(live)[0]
            self.assertEqual(result["paper_status"], "APPROVED_30D_PAPER")
            self.assertIn("APPROVED_30D_PAPER", (live / "STATUS.md").read_text())
            self.assertEqual(json.loads((account / "paper_status.json").read_text())["paper_return_pct"], 1.0)


if __name__ == "__main__":
    unittest.main()
