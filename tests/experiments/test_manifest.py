"""Coverage from a partial rerun must not erase earlier experiment provenance."""

import json
import tempfile
import unittest
from pathlib import Path

from src.research.manifest import update_manifest


class ManifestTests(unittest.TestCase):
    def test_subset_run_keeps_prior_frames_and_symbols(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            update_manifest(path, {"indicator": "rsi", "symbols": ["PLZL", "VTBR"],
                                   "timeframes": ["1H", "4H"],
                                   "late_start_by_timeframe": {"1H": "2025-01-01"}},
                            protocol_keys=("indicator",))
            update_manifest(path, {"indicator": "rsi", "symbols": ["PLZL"],
                                   "timeframes": ["15M", "30M"],
                                   "late_start_by_timeframe": {"15M": "2026-07-01"}},
                            protocol_keys=("indicator",))
            manifest = json.loads(path.read_text())
            self.assertEqual(manifest["symbols"], ["PLZL", "VTBR"])
            self.assertEqual(manifest["timeframes"], ["15M", "30M", "1H", "4H"])
            self.assertEqual(manifest["late_start_by_timeframe"],
                             {"1H": "2025-01-01", "15M": "2026-07-01"})

    def test_changed_protocol_requires_new_results_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            update_manifest(path, {"max_period": 200, "timeframes": ["1H"]},
                            protocol_keys=("max_period",))
            with self.assertRaisesRegex(ValueError, "max_period changed"):
                update_manifest(path, {"max_period": 666, "timeframes": ["30M"]},
                                protocol_keys=("max_period",))
            self.assertEqual(json.loads(path.read_text())["timeframes"], ["1H"])


if __name__ == "__main__":
    unittest.main()
