"""Each new virtual account has a validated, immutable configuration."""

import json
import tempfile
import unittest
from pathlib import Path

from papertrading.setup import load_setup


class PaperSetupTests(unittest.TestCase):
    def setUp(self):
        self.path = Path("papertrading/setups/plzl-ema12-33-1h-10pct.json")

    def test_new_plzl_setup(self):
        setup = load_setup(self.path, "ema-cross-12-33-long-short-1h")
        self.assertEqual(setup["initial_capital_rub"], 1_000_000)
        self.assertEqual(setup["position_weight_pct"], 10)
        self.assertIsNone(setup["stop_loss_pct"])

    def test_unimplemented_stop_cannot_silently_be_enabled(self):
        setup = json.loads(self.path.read_text(encoding="utf-8"))
        setup["stop_loss_pct"] = 5
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "setup.json"
            path.write_text(json.dumps(setup), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not implemented"):
                load_setup(path, "ema-cross-12-33-long-short-1h")


if __name__ == "__main__":
    unittest.main()
