"""The background worker keeps a reviewed plan and runs the ordinary pipeline."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from workers.optimization.control import start, update_job, read_job
from workers.optimization.worker import _build_and_calculate, _plan


class ImprovementWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "strategies").mkdir()
        (self.root / "strategies/catalog.json").write_text(json.dumps({"rules": [
            {"id": "test-rule", "label": "Test", "experiment": "test/parent"}]}))
        setups = self.root / "papertrading/setups/fleet"
        setups.mkdir(parents=True)
        (setups / "one.json").write_text(json.dumps({"strategy": "test-rule", "symbol": "TEST"}))
        with patch("workers.optimization.control._spawn", return_value=12345):
            self.job = start("test-rule", self.root)

    def test_plan_waits_for_user_correction(self):
        plan = {key: "text" for key in ("diagnosis", "hypothesis", "change",
                                       "lost_winners_risk", "comparison", "data_limitations")}
        with patch("workers.optimization.worker._codex", return_value=json.dumps(plan)):
            _plan(self.root, self.job["id"])
        state = read_job(self.job["id"], self.root)
        self.assertEqual(state["stage"], "WAITING_REVIEW")
        self.assertEqual(state["plan"], plan)

    def test_run_preserves_parent_and_never_passes_strategy_dir(self):
        folder = self.root / "experiments/test/improvement"
        def build(*args, **kwargs):
            folder.mkdir(parents=True)
            (folder / "protocol.json").write_text(json.dumps({"parent_strategy": "test-rule",
                                                              "parent_experiment": "test/parent"}))
            (folder / "run.py").write_text("# run")
            (folder / "review.pine").write_text("// pine")
            (folder / "results").mkdir()
            return "experiments/test/improvement"

        def pipeline(*args, **kwargs):
            (folder / "results/PIPELINE.json").write_text(json.dumps({"stage": "NEEDS_FIXED_STRATEGY"}))
            return SimpleNamespace(returncode=0)

        update_job(self.job["id"], {"stage": "RUNNING", "plan": {"hypothesis": "test"},
                                         "guidance": "keep baseline"}, self.root)
        with patch("workers.optimization.worker._codex", side_effect=build) as codex:
            with patch("workers.optimization.worker.subprocess.run", side_effect=pipeline) as run:
                _build_and_calculate(self.root, self.job["id"])
        self.assertIn("keep baseline", codex.call_args.args[3])
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["-m", "pipeline.run"])
        self.assertNotIn("--strategy-dir", command)
        state = read_job(self.job["id"], self.root)
        self.assertEqual(state["stage"], "DONE")
        self.assertEqual(state["experiment"], "experiments/test/improvement")
