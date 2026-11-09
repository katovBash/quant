"""The UI job gate must not start on an inactive strategy or skip plan review."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from workers.optimization.control import cancel, continue_job, eligible, list_jobs, start, update_job


class ImprovementControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "strategies").mkdir()
        (self.root / "strategies/catalog.json").write_text(json.dumps({"rules": [
            {"id": "test-rule", "label": "Test", "experiment": "test/parent"},
            {"id": "inactive-rule", "label": "Inactive", "experiment": "test/other"}]}))
        setups = self.root / "papertrading/setups/fleet"
        setups.mkdir(parents=True)
        (setups / "one.json").write_text(json.dumps({"strategy": "test-rule", "symbol": "TEST"}))

    def test_only_active_catalogued_strategy_can_start(self):
        self.assertEqual(eligible("test-rule", self.root), ("test/parent", "Test"))
        for name in ("inactive-rule", "../test-rule", "unknown"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                eligible(name, self.root)

    def test_plan_review_and_correction_are_required_before_run(self):
        with patch("workers.optimization.control._spawn", return_value=12345) as spawn:
            job = start("test-rule", self.root)
            with self.assertRaises(ValueError):
                continue_job(job["id"], "test", self.root)
            with self.assertRaises(ValueError):
                start("test-rule", self.root)
            update_job(job["id"], {"stage": "WAITING_REVIEW", "plan": {"hypothesis": "Filter"}}, self.root)
            running = continue_job(job["id"], "Оставить параметры Turtle", self.root)
        self.assertEqual(running["stage"], "RUNNING")
        self.assertEqual(running["guidance"], "Оставить параметры Turtle")
        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(list_jobs(self.root)[0]["id"], job["id"])

    def test_cancel_waiting_review_does_not_signal_old_worker_pid(self):
        with patch("workers.optimization.control._spawn", return_value=12345):
            job = start("test-rule", self.root)
        update_job(job["id"], {"stage": "WAITING_REVIEW"}, self.root)
        with patch("workers.optimization.control.os.killpg") as kill:
            result = cancel(job["id"], self.root)
        self.assertEqual(result["stage"], "CANCELLED")
        kill.assert_not_called()
