"""Entry-only Turtle uses prior bars and never emits a separate exit."""

import importlib.util
import unittest
from pathlib import Path


SIGNALS = Path(__file__).resolve().parents[2] / "experiments/turtle/entry-only/signals.py"
SPEC = importlib.util.spec_from_file_location("turtle_entry_only_signals", SIGNALS)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class EntryOnlySignalsTests(unittest.TestCase):
    def test_opposite_entry_replaces_exit_channel(self):
        bars = [
            {"high": 10, "low": 9, "close": 9.5},
            {"high": 11, "low": 10, "close": 10.5},
            {"high": 13, "low": 11, "close": 12},
            {"high": 12, "low": 8, "close": 8.5},
        ]
        extrema = module.prior_extrema(bars, {2})
        entries, exits = module.entry_only_from_extrema(bars, 2, extrema)
        self.assertEqual(entries, [0, 0, 1, -1])
        self.assertEqual(exits, [0, 0, 0, 0])


if __name__ == "__main__":
    unittest.main()
