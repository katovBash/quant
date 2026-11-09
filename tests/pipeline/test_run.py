"""Existing-result provenance must not impersonate a full calculation or reactivate paper."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline import run as pipeline


class PipelineRunTests(unittest.TestCase):
    def test_registered_account_count_comes_from_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            experiment = root / "experiments/example"
            results = experiment / "results"
            strategy = root / "strategies/example"
            results.mkdir(parents=True)
            strategy.mkdir(parents=True)
            (strategy / "check_parity.py").write_text("# checked by command mock\n")
            (experiment / "protocol.json").write_text("{}")
            (experiment / "run.py").write_text("# existing results\n")
            review_path = results / "paper_review.json"
            review_path.write_text(json.dumps({"rule": {"variant": "fixed"},
                                               "stocks": [{"symbol": "ABC"}]}))
            (results / "validation.json").write_text('{"structural_ok":true}')
            dividends = root / "data/dividends/moex_coverage.json"
            dividends.parent.mkdir(parents=True)
            dividends.write_text('{"status":"SUBSCRIPTION_REQUIRED"}')
            def command(*args):
                if any("activate.py" in item for item in args):
                    review = json.loads(review_path.read_text())
                    review["activation"] = {"accounts": ["A", "B", "C"]}
                    review_path.write_text(json.dumps(review))
                return ""
            with patch.object(pipeline, "ROOT", root), patch.object(
                pipeline, "command", side_effect=command), patch(
                "guardrails.lifecycle.experiment_gate", return_value=("PAPER_CANDIDATE", [])), patch(
                "guardrails.lifecycle.publish", return_value={}):
                state = pipeline.run(experiment, existing_results=True, strategy_dir=strategy)
            self.assertEqual(state["stage"], "PAPER_REGISTERED")
            self.assertEqual(state["accounts"], 3)

    def test_existing_results_revalidate_without_rerun_or_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            experiment = root / "experiments/example"
            results = experiment / "results"
            results.mkdir(parents=True)
            (experiment / "protocol.json").write_text("{}")
            (experiment / "run.py").write_text("raise AssertionError('must not run')\n")
            (results / "paper_review.json").write_text(json.dumps({
                "activation": {"accounts": ["EXAMPLE-1"]}, "stocks": [],
                "validation": {"structural_ok": False}}))
            (results / "validation.json").write_text('{"structural_ok":true}')
            dividends = root / "data/dividends/moex_coverage.json"
            dividends.parent.mkdir(parents=True)
            dividends.write_text('{"status":"SUBSCRIPTION_REQUIRED"}')
            calls = []
            with patch.object(pipeline, "ROOT", root), patch.object(
                pipeline, "command", side_effect=lambda *args: calls.append(args)), patch(
                "guardrails.lifecycle.experiment_gate", side_effect=lambda review: (
                    "PAPER_CANDIDATE" if review["validation"]["structural_ok"] else "EXPERIMENT_REVIEW", [])):
                state = pipeline.run(experiment, existing_results=True)
            self.assertEqual(state["run_mode"], "existing_results_revalidated")
            self.assertEqual(state["stage"], "PAPER_REGISTERED_EXISTING")
            self.assertEqual(state["accounts"], 1)
            self.assertEqual(len(calls), 2)
            self.assertIn("validate_run.py", calls[0][0])
            self.assertIn("build_experiment_packages.py", calls[1][0])
            self.assertEqual(json.loads((results / "paper_review.json").read_text())[
                "activation"]["accounts"], ["EXAMPLE-1"])


if __name__ == "__main__":
    unittest.main()
