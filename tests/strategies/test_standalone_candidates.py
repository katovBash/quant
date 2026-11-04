"""Frozen strategy signals must match the research rule at completed bars."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from src.research.standalone_grid import ema_level_signals, load_bars, variants

ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ("rsi-21-60-40-long-short-1h", "rsi", "SFIN", "rsi_21_60_40"),
    ("adx-di-14-20-long-short-1h", "adx", "PLZL", "adx_di_14_20"),
    ("four-point-levels-5-1p5-long-short-1h", "four_point_levels", "KOGK", "four_points_5_1.5"),
    ("breakout-20-long-short-1h", "patterns", "PLZL", "breakout_20"),
)


class CandidateParityTests(unittest.TestCase):
    def test_ema_level_smlt_signals_match_research(self):
        selected = (
            ("ema-level-45-atr025-long-short-1h", "SMLT", "1H", 45, 0.25),
            ("ema-level-79-atr025-long-short-1h", "WUSH", "1H", 79, 0.25),
            ("ema-level-94-atr05-long-short-1h", "SFIN", "1H", 94, 0.5),
            ("ema-level-25-atr05-long-short-1d", "SMLT", "1D", 25, 0.5),
        )
        for slug, symbol, timeframe, period, width in selected:
            path = ROOT / "strategies" / slug / "strategy.py"
            spec = importlib.util.spec_from_file_location(slug.replace("-", "_"), path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            bars = load_bars(symbol, timeframe)
            research = ema_level_signals(bars, period, width)
            first = [i + 1 for i, event in enumerate(research) if event][:5]
            last = [i + 1 for i, event in enumerate(research) if event][-5:]
            for count in sorted(set([period, 100, 500, len(bars), *first, *last])):
                with self.subTest(slug=slug, bars=count):
                    self.assertEqual(module.signal(bars[:count]), research[count - 1])

    def test_selected_signals_match_research(self):
        for slug, family, symbol, variant in CASES:
            path = ROOT / "strategies" / slug / "strategy.py"
            spec = importlib.util.spec_from_file_location(slug.replace("-", "_"), path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            bars = load_bars(symbol, "1H")
            research = next(signals for name, _, signals in variants(family, bars) if name == variant)
            signal_bars = []
            for side in (1, -1):
                matches = [index + 1 for index, value in enumerate(research) if value == side and index >= 33]
                signal_bars.extend(matches[:2] + matches[-2:])
            for index in sorted(set((100, 250, 500, len(bars), *signal_bars))):
                with self.subTest(slug=slug, bars=index):
                    self.assertEqual(module.signal(bars[:index]), research[index - 1])


if __name__ == "__main__":
    unittest.main()
