"""Discovery never repeats a day, a hypothesis or work after the off switch."""

import json
import tempfile
import unittest
from pathlib import Path

from workers.discovery.control import set_enabled, status
from workers.discovery.daily import finalize, fingerprint, run_daily


CANDIDATE = {
    "status": "IDEA", "indicator_id": "sample-indicator", "run_id": "third-touch",
    "source_url": "https://example.org/paper", "source_evidence": "Section 2, rule A",
    "hypothesis": "Third contact may reverse", "signal_rule": "two confirmed pivots define a line",
    "entry_rule": "third touch enters away", "exit_rule": "opposite line closes",
    "indicator_roles": ["support", "resistance"], "timeframes": ["1H", "1D"],
    "parameter_axes": {"wing": [3, 5]}, "excluded_variants": [],
    "next_research": "Test breakout instead of bounce",
}


class DailyDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "experiments").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_off_is_default_and_run_does_not_write_or_call_planner(self):
        calls = []
        actual = run_daily(self.root, day="2026-11-07",
                           planner=lambda *_: calls.append("planner"))
        self.assertEqual(actual["status"], "DISABLED")
        self.assertEqual(calls, [])
        self.assertFalse((self.root / "workers/discovery/runtime").exists())

    def test_toggle_persists_and_same_day_is_idempotent(self):
        set_enabled(True, self.root)
        calls = []

        def build(root, day, candidate):
            calls.append("build")
            folder = root / "experiments" / candidate["indicator_id"] / candidate["run_id"]
            folder.mkdir(parents=True)
            (folder / "run.py").write_text("# runner\n")
            (folder / "review.pine").write_text("//@version=6\n")
            (folder / "protocol.json").write_text(json.dumps({
                "indicator_id": candidate["indicator_id"], "run_id": candidate["run_id"],
                "status": "PREREGISTERED", "expected_variants": ["baseline", "test"],
                "parameter_grid": {"axes": {"wing": {"values": [3, 5]}}},
                "signal_timeframes": candidate["timeframes"],
                "source_url": candidate["source_url"], "signal_rule": candidate["signal_rule"],
                "entry_rule": candidate["entry_rule"], "exit_rule": candidate["exit_rule"],
                "eligible_universe": {"snapshot_file": "universe.json"},
                "corporate_actions": {"status": "unchecked"}, "cost_status": "costs",
                "start": "2024-01-01", "split": "2026-01-01", "selection": "fixed",
                "run_command": "python3 run.py"}))

        def pipeline(experiment, **kwargs):
            calls.append("pipeline")
            return {"stage": "REVIEW_REQUIRED", "warnings": ["only 6 stocks"]}

        first = run_daily(self.root, day="2026-11-07", planner=lambda *_: dict(CANDIDATE),
                          builder=build, pipeline_runner=pipeline)
        self.assertEqual(first["status"], "REVIEW_REQUIRED")
        self.assertEqual(calls, ["build", "pipeline"])
        self.assertEqual(status(self.root)["last_run_day"], "2026-11-07")
        protocol = json.loads((self.root / first["experiment"] / "protocol.json").read_text())
        self.assertEqual(protocol["discovery"]["fingerprint"], fingerprint(CANDIDATE))
        report = self.root / status(self.root)["last_report"]
        self.assertIn("only 6 stocks", report.read_text())

        again = run_daily(self.root, day="2026-11-07", planner=lambda *_: self.fail("planned twice"))
        self.assertEqual(again["status"], "ALREADY_DONE")
        duplicate = run_daily(self.root, day="2026-11-08", planner=lambda *_: dict(CANDIDATE),
                              builder=lambda *_: self.fail("rebuilt duplicate"))
        self.assertEqual(duplicate["status"], "DUPLICATE")
        self.assertEqual(calls, ["build", "pipeline"])

    def test_turning_off_during_build_stops_before_pipeline(self):
        set_enabled(True, self.root)

        def build(root, day, candidate):
            folder = root / "experiments" / candidate["indicator_id"] / candidate["run_id"]
            folder.mkdir(parents=True)
            (folder / "run.py").write_text("# runner\n")
            (folder / "review.pine").write_text("//@version=6\n")
            (folder / "protocol.json").write_text(json.dumps({
                "indicator_id": candidate["indicator_id"], "run_id": candidate["run_id"],
                "status": "PREREGISTERED", "expected_variants": ["baseline", "test"],
                "parameter_grid": {"axes": {"wing": {"values": [3, 5]}}},
                "signal_timeframes": candidate["timeframes"],
                "source_url": candidate["source_url"], "signal_rule": candidate["signal_rule"],
                "entry_rule": candidate["entry_rule"], "exit_rule": candidate["exit_rule"],
                "eligible_universe": {"snapshot_file": "universe.json"},
                "corporate_actions": {"status": "unchecked"}, "cost_status": "costs",
                "start": "2024-01-01", "split": "2026-01-01", "selection": "fixed",
                "run_command": "python3 run.py"}))
            set_enabled(False, root)

        result = run_daily(self.root, day="2026-11-07", planner=lambda *_: dict(CANDIDATE),
                           builder=build,
                           pipeline_runner=lambda *_: self.fail("pipeline after off"))
        self.assertEqual(result["status"], "STOPPED")
        self.assertFalse(status(self.root)["enabled"])
        set_enabled(True, self.root)
        retry = run_daily(self.root, day="2026-11-07", retry=True,
                          planner=lambda *_: self.fail("planned reserved hypothesis twice"))
        self.assertEqual(retry["status"], "RECOVERY_REQUIRED")
        self.assertIn("python3 -m pipeline.run", retry["next_action"])

    def test_no_idea_writes_day_report_without_registering_experiment(self):
        set_enabled(True, self.root)
        result = run_daily(self.root, day="2026-11-07", planner=lambda *_: {
            "status": "NO_IDEA", "reason": "No verifiable source", "next_research": "Try next paper"})
        self.assertEqual(result["status"], "NO_IDEA")
        self.assertIn("No verifiable source", (self.root / status(self.root)["last_report"]).read_text())
        self.assertFalse((self.root / "workers/discovery/runtime/registry.json").exists())
        calls = []
        retry = run_daily(self.root, day="2026-11-07", retry=True,
                          planner=lambda *_: (calls.append("plan") or {
                              "status": "NO_IDEA", "reason": "Still no source"}))
        self.assertEqual(retry["status"], "NO_IDEA")
        self.assertEqual(calls, ["plan"])

    def test_native_automation_prepared_candidate_uses_pipeline_without_nested_codex(self):
        set_enabled(True, self.root)
        candidate_file = self.root / "workers/discovery/runtime/candidate.json"
        candidate_file.write_text(json.dumps(CANDIDATE))
        folder = self.root / "experiments/sample-indicator/third-touch"
        folder.mkdir(parents=True)
        (folder / "run.py").write_text("# runner\n")
        (folder / "review.pine").write_text("//@version=6\n")
        (folder / "protocol.json").write_text(json.dumps({
            "indicator_id": CANDIDATE["indicator_id"], "run_id": CANDIDATE["run_id"],
            "status": "PREREGISTERED", "source_url": CANDIDATE["source_url"],
            "signal_rule": CANDIDATE["signal_rule"], "entry_rule": CANDIDATE["entry_rule"],
            "exit_rule": CANDIDATE["exit_rule"], "signal_timeframes": CANDIDATE["timeframes"],
            "parameter_grid": {"axes": {"wing": {"values": [3, 5]}}},
            "expected_variants": ["baseline", "test3", "test5"],
            "eligible_universe": {"snapshot_file": "universe.json"},
            "corporate_actions": {"status": "unchecked"}, "cost_status": "costs",
            "start": "2024-01-01", "split": "2026-01-01", "selection": "fixed",
            "run_command": "python3 run.py"}))
        result = run_daily(self.root, day="2026-11-07", candidate_file=candidate_file,
                           prepared=True, planner=lambda *_: self.fail("nested planner"),
                           builder=lambda *_: self.fail("nested builder"),
                           strategy_builder=lambda *_: self.fail("nested strategy builder"),
                           pipeline_runner=lambda *_: {"stage": "NEEDS_FIXED_STRATEGY"})
        self.assertEqual(result["status"], "NEEDS_FIXED_STRATEGY")
        self.assertEqual(status(self.root)["last_result"], "NEEDS_FIXED_STRATEGY")
        (folder / "results").mkdir()
        (folder / "results/PIPELINE.json").write_text(json.dumps({
            "stage": "PAPER_REGISTERED", "warnings": []}))
        final = finalize(self.root, folder)
        self.assertEqual(final["status"], "PAPER_REGISTERED")
        self.assertEqual(status(self.root)["last_result"], "PAPER_REGISTERED")
        self.assertIn("PAPER_REGISTERED", (self.root / status(self.root)["last_report"]).read_text())


if __name__ == "__main__":
    unittest.main()
