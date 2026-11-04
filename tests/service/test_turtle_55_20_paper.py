"""Ensure the paper signal is the frozen experiment's Turtle 55/20 rule."""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


paper = module_at("paper_turtle_55_20", ROOT / "strategies/dennis-turtle-55-20-1h/strategy.py")
research = module_at("research_turtle_55_20", ROOT / "experiments/three-trader-rules/signals.py")


class FrozenTurtleSignalTest(unittest.TestCase):
    def test_paper_matches_research_entries_and_exits(self):
        for symbol in ("SFIN", "WUSH"):
            path = ROOT / f"data/moex_scan/{symbol}_60_2024-01-01_2026-10-30.json"
            bars = json.loads(path.read_text(encoding="utf-8"))
            entries, exits = research.turtle(bars, 55, 20)
            for index in range(200, len(bars), 47):
                for position in (0, 100, -100):
                    expected = ("long" if entries[index] == 1 else
                                "short" if entries[index] == -1 else
                                "flat" if position > 0 and exits[index] == -1 else
                                "flat" if position < 0 and exits[index] == 1 else None)
                    self.assertEqual(paper.signal(bars[:index + 1], position=position),
                                     expected, (symbol, index, position))


if __name__ == "__main__":
    unittest.main()
