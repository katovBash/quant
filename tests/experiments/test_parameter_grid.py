"""The declared domain must generate every admissible variant."""

import unittest

from src.research.parameter_grid import variants_from_grid


class ParameterGridTests(unittest.TestCase):
    def test_single_ema_inclusive_1_to_300(self):
        result = variants_from_grid({"axes": {"period": {"start": 1, "stop": 300}},
                                     "variant_template": "ema_{period}"})
        self.assertEqual(len(result), 301)
        self.assertEqual(result[1], "ema_1")
        self.assertEqual(result[-1], "ema_300")

    def test_fast_slow_constraint_removes_invalid_pairs(self):
        result = variants_from_grid({
            "axes": {"fast": {"start": 1, "stop": 3}, "slow": {"start": 1, "stop": 3}},
            "less_than": [["fast", "slow"]],
            "variant_template": "ema_{fast}_{slow}"})
        self.assertEqual(result, ["baseline", "ema_1_2", "ema_1_3", "ema_2_3"])

    def test_huge_grid_requires_explicit_scope_decision(self):
        with self.assertRaisesRegex(ValueError, "max_combinations"):
            variants_from_grid({"axes": {"a": {"start": 1, "stop": 300},
                                         "b": {"start": 1, "stop": 300},
                                         "c": {"start": 1, "stop": 300}},
                                "variant_template": "x_{a}_{b}_{c}"})

    def test_fractional_indicator_values_are_not_rounded(self):
        result = variants_from_grid({"axes": {"atr": {"values": [0.25, 0.5, 1, 1.5]}},
                                     "variant_template": "atr_{atr}"})
        self.assertEqual(result, ["baseline", "atr_0.25", "atr_0.5", "atr_1", "atr_1.5"])

    def test_fractional_range_includes_last_value(self):
        result = variants_from_grid({"axes": {"threshold": {"start": 0.25, "stop": 1.0,
                                                              "step": 0.25}},
                                     "variant_template": "threshold_{threshold}"})
        self.assertEqual(result[-1], "threshold_1")
        self.assertEqual(len(result), 5)

    def test_grouped_controls_and_factorial_combination(self):
        result = variants_from_grid({"groups": [
            {"axes": {"a": {"values": [1, 2]}}, "variant_template": "a_{a}"},
            {"axes": {"b": {"values": [3]}}, "variant_template": "b_{b}"},
            {"axes": {"a": {"values": [1, 2]}, "b": {"values": [3]}},
             "variant_template": "ab_{a}_{b}"}], "max_combinations": 5})
        self.assertEqual(result, ["baseline", "a_1", "a_2", "b_3", "ab_1_3", "ab_2_3"])


if __name__ == "__main__":
    unittest.main()
