"""Review must inspect every fixed rule before describing the experiment."""

import csv
import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


PREPARE = Path(__file__).resolve().parents[2] / "skills/experiment-paper-review/scripts/prepare.py"
spec = importlib.util.spec_from_file_location("paper_review_prepare", PREPARE)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ReviewScreeningTests(unittest.TestCase):
    def test_controls_can_be_excluded_from_promotion_without_removing_results(self):
        metrics = {("S", "4H", "tc_a_d_t3"): {"train_returns": [10, 10, 10],
                                                  "train_pnls": [1, 1, 1],
                                                  "late_returns": [10], "late_pnls": [1]},
                   ("S", "4H", "pc_a_d_t3"): {"train_returns": [1, 1, 1],
                                                  "train_pnls": [1, 1, 1],
                                                  "late_returns": [1], "late_pnls": [1]}}
        chosen, ranked = prepare.choose_global_rule(metrics, min_symbols=1,
                                                     variant_prefixes=("pc_",))
        self.assertEqual(chosen["variant"], "pc_a_d_t3")
        self.assertEqual(len(ranked), 1)

    def test_later_rule_with_fewer_than_ten_stocks_is_recorded_when_first_has_zero(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "monthly_returns.csv"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "symbol", "timeframe", "variant", "start",
                    "starting_equity_rub", "ending_equity_rub"])
                writer.writeheader()
                for variant, return_pct in (("first", 5), ("second", 15)):
                    for index in range(8):
                        for month in range(1, 13):
                            writer.writerow({"symbol": f"S{index}", "timeframe": "1H",
                                             "variant": variant,
                                             "start": f"2025-{month:02d}-01",
                                             "starting_equity_rub": 1_000_000,
                                             "ending_equity_rub": 1_000_000 *
                                             (1 + return_pct / 100)})
            rules = [{"timeframe": "1H", "variant": variant}
                     for variant in ("first", "second")]
            def liquid(rule, _metrics, _rows, limit=None):
                return ([{"symbol": f"S{index}"} for index in range(8)],
                        {"turnover_threshold_rub": 1})
            with patch.object(prepare, "select_stocks", side_effect=liquid):
                screened = prepare.screen_every_rule(rules, {}, {}, path, "after_costs")
            self.assertEqual([row["passed_trailing_12m"] for row in screened], [0, 8])
            self.assertFalse(screened[0]["has_paper_candidates"])
            self.assertTrue(screened[1]["has_paper_candidates"])
            chosen, evidence = prepare.first_passing_rule(rules, screened)
            self.assertEqual(chosen["variant"], "second")
            self.assertEqual(evidence["passed_trailing_12m"], 8)
            with patch.object(prepare, "select_stocks", side_effect=liquid):
                gross = prepare.screen_every_rule(rules, {}, {}, path, "gross_before_costs")
            self.assertEqual([row["passed_trailing_12m"] for row in gross], [None, None])


if __name__ == "__main__":
    unittest.main()
