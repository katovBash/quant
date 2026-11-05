import unittest

from src.research.combination_review import audit


class CombinationReviewTests(unittest.TestCase):
    def test_requires_both_controls_and_combination_for_every_pair(self):
        protocol = {"expected_variants": ["baseline", "a", "b", "ab"],
                    "combination_design": {"scope": "fixed_parameter_transfer",
                                           "components": [
                                               {"name": "A", "controls": ["a"], "parameters": {"period": [25]}},
                                               {"name": "B", "controls": ["b"], "parameters": {"period": [30]}}],
                                           "combined_variants": ["ab"]}}
        rows = [{"symbol": symbol, "timeframe": "1H", "variant": variant}
                for symbol in ("AAA", "BBB") for variant in ("baseline", "a", "b", "ab")]
        self.assertTrue(audit(protocol, rows)["ok"])
        missing = audit(protocol, rows[:-1])
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["missing_examples"], [("BBB", "1H", "ab")])
        protocol["combination_design"]["scope"] = "full_factorial"
        protocol["combination_design"]["factorial_axes"] = ["a_period", "b_period"]
        protocol["parameter_grid"] = {"axes": {"a_period": {"values": [25]}}}
        self.assertFalse(audit(protocol, rows)["ok"])
        protocol["parameter_grid"]["axes"]["b_period"] = {"values": [30]}
        self.assertTrue(audit(protocol, rows)["ok"])


if __name__ == "__main__":
    unittest.main()
