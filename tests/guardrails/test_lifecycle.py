"""Lifecycle labels must follow recorded evidence and never enable real orders."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from guardrails.lifecycle import account_gate, build, experiment_gate
from guardrails.policy import load_policy


class LifecycleTests(unittest.TestCase):
    def test_closed_experiment_cannot_reenter_paper_gate(self):
        review = {"decision": {"status": "CLOSED", "reason": "insufficient monthly consistency"},
                  "validation": {"structural_ok": True},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"candle_quality": {"status": "basic_check_ok"}} for _ in range(10)]}
        self.assertEqual(experiment_gate(review),
                         ("EXPERIMENT_CLOSED", ["insufficient monthly consistency"]))

    def test_experiment_gate_allows_virtual_review_with_explicit_corporate_warning(self):
        review = {"validation": {"structural_ok": True,
                                 "corporate_actions": {"status": "partial"},
                                 "monthly_validation": {"gap_pairs": 2}},
                  "protocol": {"cost_status": "after_costs"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"candle_quality": {"status": "basic_check_ok"}}
                             for _ in range(10)]}
        gate, warnings = experiment_gate(review)
        self.assertEqual(gate, "PAPER_CANDIDATE")
        self.assertTrue(any("дивидендов" in warning for warning in warnings))
        review["protocol"]["cost_status"] = "gross_before_costs"
        self.assertEqual(experiment_gate(review)[0], "EXPERIMENT_REVIEW")

    def test_account_loss_requires_review(self):
        self.assertEqual(account_gate("NOT_APPROVED_30D"), "PAPER_STOP_REVIEW")
        self.assertEqual(account_gate("COSTS_UNVERIFIED"), "COST_REVIEW")

    def test_unverified_historical_costs_cannot_register_paper(self):
        review = {"validation": {"structural_ok": True},
                  "protocol": {"cost_status": "historical_cost_model_incomplete"},
                  "rule": {"variant": "fixed"},
                  "stocks": [{"candle_quality": {"status": "basic_check_ok"}}
                             for _ in range(load_policy()["experiment"]["paper_stock_count"])]}
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
                "stocks": [{"candle_quality": {"status": "basic_check_ok"}}
                           for _ in range(load_policy()["experiment"]["paper_stock_count"])]}))
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
            self.assertEqual(result["strategies"][0]["stage"], "PAPER_QUEUED")
            self.assertFalse(result["real_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
