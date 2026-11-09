"""Lifecycle labels must follow recorded evidence and never enable real orders."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from guardrails.lifecycle import account_gate, build, experiment_gate
from guardrails.policy import load_policy
from eval.historical import rolling_three_months, selected_history_gate


class LifecycleTests(unittest.TestCase):
    def test_new_review_requires_full_grid_screening_before_paper(self):
        review = {"review_version": 2, "validation": {"structural_ok": True},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"timeframe": "1H", "variant": "fixed"},
                  "stocks": [{"symbol": f"S{i}", "candle_quality": {"status": "basic_check_ok"},
                              "recent_periods": {"12": {"return_pct": 11,
                                                        "from_month": "2025-10", "through_month": "2026-09"}}}
                             for i in range(10)]}
        self.assertEqual(experiment_gate(review)[0], "EXPERIMENT_REVIEW")
        review["candidate_rules"] = [review["rule"]]
        review["rule_screening"] = [{"timeframe": "1H", "variant": "fixed",
                                      "passed_trailing_12m": 10}]
        review["screening_summary"] = {"rules_checked": 1, "best_by_train_passed": 10}
        self.assertEqual(experiment_gate(review)[0], "PAPER_CANDIDATE")
        review["screening_summary"]["best_by_train_passed"] = 0
        self.assertEqual(experiment_gate(review)[0], "EXPERIMENT_REVIEW")

    def test_closed_experiment_cannot_reenter_paper_gate(self):
        review = {"decision": {"status": "CLOSED", "reason": "insufficient monthly consistency"},
                  "validation": {"structural_ok": True},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"candle_quality": {"status": "basic_check_ok"}} for _ in range(10)]}
        self.assertEqual(experiment_gate(review),
                         ("EXPERIMENT_CLOSED", ["insufficient monthly consistency"]))

    def test_one_passing_stock_can_be_paper_candidate(self):
        review = {"review_version": 2, "validation": {"structural_ok": True},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"timeframe": "4H", "variant": "fixed"},
                  "stocks": [{"symbol": "SFIN", "candle_quality": {"status": "basic_check_ok"},
                              "recent_periods": {"12": {"return_pct": 29.27,
                                                        "from_month": "2025-10",
                                                        "through_month": "2026-09"}}}],
                  "candidate_rules": [{"timeframe": "4H", "variant": "fixed"}],
                  "rule_screening": [{"timeframe": "4H", "variant": "fixed",
                                      "passed_trailing_12m": 1}],
                  "screening_summary": {"rules_checked": 1, "best_by_train_passed": 1}}
        self.assertEqual(experiment_gate(review)[0], "PAPER_CANDIDATE")

    def test_first_train_rank_with_passing_stocks_can_skip_zero_rule(self):
        review = {"review_version": 2, "selection_scope": "all_passing",
                  "selection_method": "first_train_rank_with_passing_stocks",
                  "validation": {"structural_ok": True},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"timeframe": "4H", "variant": "second"},
                  "candidate_rules": [{"timeframe": "4H", "variant": "first"},
                                      {"timeframe": "4H", "variant": "second"}],
                  "rule_screening": [{"timeframe": "4H", "variant": "first",
                                      "passed_trailing_12m": 0},
                                     {"timeframe": "4H", "variant": "second",
                                      "passed_trailing_12m": 1}],
                  "screening_summary": {"rules_checked": 2, "selected_passed": 1},
                  "stocks": [{"symbol": "SFIN", "candle_quality": {"status": "basic_check_ok"},
                              "recent_periods": {"12": {"return_pct": 29.27,
                                                        "from_month": "2025-10",
                                                        "through_month": "2026-09"}}}]}
        self.assertEqual(experiment_gate(review)[0], "PAPER_CANDIDATE")
        review["rule"]["variant"] = "first"
        self.assertEqual(experiment_gate(review)[0], "EXPERIMENT_REVIEW")

    def test_experiment_gate_allows_virtual_review_with_explicit_corporate_warning(self):
        review = {"validation": {"structural_ok": True,
                                 "corporate_actions": {"status": "partial"},
                                 "monthly_validation": {"gap_pairs": 2}},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"symbol": f"S{i}", "candle_quality": {"status": "basic_check_ok"},
                              "recent_periods": {"12": {"return_pct": 10.01,
                                                        "from_month": "2025-10", "through_month": "2026-09"}}}
                             for i in range(10)]}
        gate, warnings = experiment_gate(review)
        self.assertEqual(gate, "PAPER_CANDIDATE")
        self.assertTrue(any("дивидендов" in warning for warning in warnings))
        review["protocol"]["cost_status"] = "gross_before_costs"
        self.assertEqual(experiment_gate(review)[0], "EXPERIMENT_REVIEW")

    def test_trailing_year_threshold_blocks_low_return_and_missing_window(self):
        review = {"validation": {"structural_ok": True},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"symbol": f"S{i}", "candle_quality": {"status": "basic_check_ok"},
                              "recent_periods": {"12": {"return_pct": 10.01,
                                                        "from_month": "2025-10", "through_month": "2026-09"}}}
                             for i in range(10)]}
        self.assertEqual(experiment_gate(review)[0], "PAPER_CANDIDATE")
        review["stocks"][0]["recent_periods"]["12"]["return_pct"] = 10
        gate, reasons = experiment_gate(review)
        self.assertEqual(gate, "RETURN_BELOW_PAPER_THRESHOLD")
        self.assertIn("S0", reasons[0])
        del review["stocks"][0]["recent_periods"]["12"]
        self.assertEqual(experiment_gate(review)[0], "RETURN_BELOW_PAPER_THRESHOLD")

    def test_registered_one_stock_strategy_fails_selection_and_return(self):
        selection = {"top10": [{"symbol": "MGNT"}]}
        history = {"symbols": {"MGNT": {"after": {"periods": {"12": {
            "return_pct": -1.18, "from_month": "2025-10", "through_month": "2026-09"}}}}}}
        passed, failures = selected_history_gate(selection, history)
        self.assertFalse(passed)
        self.assertTrue(any("-1.18%" in reason for reason in failures))

    def test_rolling_three_months_uses_complete_consecutive_months(self):
        months = [{"month": "2026-01", "return_pct": 10},
                  {"month": "2026-02", "return_pct": -5},
                  {"month": "2026-03", "return_pct": 2},
                  {"month": "2026-05", "return_pct": 1}]
        windows = rolling_three_months(months)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["return_pct"], 6.59)

    def test_account_loss_requires_review(self):
        self.assertEqual(account_gate("NOT_APPROVED_30D"), "PAPER_STOP_REVIEW")
        self.assertEqual(account_gate("COSTS_UNVERIFIED"), "COST_REVIEW")

    def test_unverified_historical_costs_cannot_register_paper(self):
        review = {"validation": {"structural_ok": True},
                  "protocol": {"cost_status": "historical_cost_model_incomplete"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"candle_quality": {"status": "basic_check_ok"}}
                             for _ in range(load_policy()["experiment"]["min_paper_stocks"])]}
        self.assertEqual(experiment_gate(review)[0], "EXPERIMENT_REVIEW")

    def test_forward_statistical_label_is_not_needed_for_exit_review(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            live, setups, strategies = (root / name for name in ("live", "setups", "strategies"))
            for folder in (live / "ABC-EXAMPLE", setups, strategies / "example"):
                folder.mkdir(parents=True)
            (setups / "example.json").write_text(json.dumps({
                "strategy": "example", "account_id": "ABC-EXAMPLE", "symbol": "ABC"}))
            source = root / "paper_review.json"
            source.write_text(json.dumps({
                "validation": {"structural_ok": True, "corporate_actions": {"status": "complete"}},
                "protocol": {"cost_status": "after_costs"},
                "rule": {"variant": "fixed"},
                "stocks": [{"symbol": f"S{i}", "candle_quality": {"status": "basic_check_ok"},
                            "recent_periods": {"12": {"return_pct": 11,
                                                      "from_month": "2025-10", "through_month": "2026-09"}}}
                           for i in range(load_policy()["experiment"]["min_paper_stocks"])]}))
            (strategies / "example" / "selection.json").write_text(json.dumps({
                "source_review": str(source)}))
            (live / "ABC-EXAMPLE" / "paper_status.json").write_text(json.dumps({
                "paper_status": "APPROVED_30D_PAPER", "paper_calendar_days": 30,
                "paper_return_pct": 1.0}))
            # build resolves source paths against the repository root; use a relative
            # source only in production. Here the source is absolute and joins safely.
            self.assertEqual(build(live, setups, strategies)["strategies"][0]["stage"], "EXIT_REVIEW")

    def test_new_setups_are_queued_without_live_equity(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            live, setups, strategies = (root / name for name in ("live", "setups", "strategies"))
            for folder in (live, setups, strategies / "example"):
                folder.mkdir(parents=True)
            (setups / "example.json").write_text(json.dumps({
                "strategy": "example", "account_id": "ABC-EXAMPLE", "symbol": "ABC"}))
            result = build(live, setups, strategies)
            self.assertEqual(result["strategies"][0]["stage"], "PAPER_GATE_FAILED")
            self.assertFalse(result["real_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
