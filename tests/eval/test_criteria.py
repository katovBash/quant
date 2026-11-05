"""Regression checks for forward evidence and paper review."""

import unittest
from datetime import date, timedelta

from eval.evaluate import evaluate
class ForwardGateTests(unittest.TestCase):
    def setUp(self):
        first = date(2027, 1, 1)
        self.dates = [first + timedelta(days=i) for i in range(260)]
        self.baseline = [100.0 for _ in self.dates]
        self.strategy = [100 * 1.001 ** i for i in range(260)]

    def test_hundred_trades_alone_is_insufficient(self):
        result = evaluate(self.dates, self.strategy, self.baseline, 100,
                          costs_verified=False, draws=100)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")

    def test_positive_forward_edge_needs_control_and_costs(self):
        result = evaluate(self.dates, self.strategy, self.baseline, 110,
                          costs_verified=True, draws=300)
        self.assertEqual(result["status"], "FORWARD_EVIDENCE_OF_EDGE")

    def test_identical_control_is_not_edge(self):
        result = evaluate(self.dates, self.baseline, self.baseline, 110,
                          costs_verified=True, draws=100)
        self.assertEqual(result["status"], "NO_RELIABLE_EDGE_DETECTED")

    def test_short_requires_own_expense_check(self):
        result = evaluate(self.dates, self.strategy, self.baseline, 110,
                          costs_verified=True, has_short=True, draws=100)
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")

    def test_positive_thirty_calendar_days_approves_paper_only(self):
        result = evaluate(self.dates[:31], self.strategy[:31], self.baseline[:31], 1,
                          costs_verified=True, draws=100)
        self.assertEqual(result["paper_status"], "APPROVED_30D_PAPER")
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")

    def test_thirty_day_paper_needs_positive_return_and_verified_costs(self):
        early = evaluate(self.dates[:30], self.strategy[:30], self.baseline[:30], 1,
                         costs_verified=True, draws=100)
        self.assertEqual(early["paper_status"], "OBSERVING")
        losing = [100 * 0.999 ** i for i in range(31)]
        negative = evaluate(self.dates[:31], losing, self.baseline[:31], 1,
                            costs_verified=True, draws=100)
        self.assertEqual(negative["paper_status"], "NOT_APPROVED_30D")
        unverified = evaluate(self.dates[:31], self.strategy[:31], self.baseline[:31], 1,
                              costs_verified=True, has_short=True, draws=100)
        self.assertEqual(unverified["paper_status"], "COSTS_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
