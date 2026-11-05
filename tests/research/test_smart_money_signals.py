import json
import unittest
from pathlib import Path

from src.research.smart_money_signals import all_variants


ROOT = Path(__file__).resolve().parents[2]


class SmartMoneySignalTests(unittest.TestCase):
    def test_sweep_then_fvg_is_causal_and_matches_frozen_grid(self):
        bars = [{"ts": f"2026-01-{i+1:02d}T00:00:00", "open": 10.0, "high": 10.2,
                 "low": 9.8, "close": 10.0, "volume": 1000} for i in range(20)]
        bars[14].update(open=9.7, high=10.2, low=8.5, close=10.0)
        bars[15].update(open=10.5, high=11.2, low=10.4, close=11.0)
        rules = all_variants(bars)
        protocol = json.loads((ROOT / "experiments/smart-money/liquidity-sweep-fvg/protocol.json").read_text())
        self.assertEqual(set(rules) | {"baseline"}, set(protocol["expected_variants"]))
        self.assertEqual(rules["sweep_10_0"][0][14], 1)
        self.assertEqual(rules["fvg_0.2"][0][15], 1)
        self.assertEqual(rules["smc_10_0_0.2_1"][0][15], 1)
        self.assertEqual(rules["smc_10_0_0.2_1"][0][14], 0)
        changed = [dict(bar) for bar in bars]
        changed[19].update(high=50, low=1, close=2)
        self.assertEqual(all_variants(changed)["smc_10_0_0.2_1"][0][:19],
                         rules["smc_10_0_0.2_1"][0][:19])


if __name__ == "__main__":
    unittest.main()
