import math
import unittest

from src.research.market_regime import classify, forecast


def bars(n=130):
    from datetime import datetime, timedelta
    start = datetime(2026, 1, 1)
    out = []
    for i in range(n):
        price = 100 + 0.12 * i + 2 * math.sin(i / 5)
        out.append({"ts": (start + timedelta(days=i)).strftime("%Y-%m-%d 12:00:00"),
                    "open": price - 0.2, "high": price + 1, "low": price - 1,
                    "close": price, "volume": 1000})
    return out


CONFIG = {"lookback": 20, "max_width_atr": 6, "min_displacement_atr": 2}


class MarketRegimeTests(unittest.TestCase):
    def test_labels_are_past_only_and_range_is_inside_frozen_bounds(self):
        history = bars()
        original = classify(history, **CONFIG)
        changed = bars()
        changed[-1].update(open=20, high=300, low=10, close=250)
        updated = classify(changed, **CONFIG)
        self.assertEqual(original[:-1], updated[:-1])
        self.assertEqual(original[-1]["support"], updated[-1]["support"])
        self.assertEqual(original[-1]["resistance"], updated[-1]["resistance"])
        for bar, state in zip(history, original):
            if state["label"] == "range":
                self.assertLessEqual(state["support"], bar["close"])
                self.assertLessEqual(bar["close"], state["resistance"])

    def test_forecast_outcome_does_not_cross_split(self):
        history = bars()
        labels = classify(history, **CONFIG)
        split = history[75]["ts"][:10]
        first = forecast(history, labels, 5, split, "TEST", "1D", CONFIG)
        changed = [dict(x) for x in history]
        for item in changed[75:]:
            item["close"] *= 1.5
        second = forecast(changed, labels, 5, split, "TEST", "1D", CONFIG)
        self.assertEqual([r for r in first if r["sample"] == "train"],
                         [r for r in second if r["sample"] == "train"])

    def test_hit_rate_is_compared_with_unconditional_frequency(self):
        history = bars()
        labels = classify(history, **CONFIG)
        rows = forecast(history, labels, 5, history[75]["ts"][:10], "TEST", "1D", CONFIG)
        self.assertEqual(len(rows), 8)
        for row in rows:
            self.assertNotIn("net_return_pct", row)
            if row["observations"] and row["label"] != "uncertain":
                self.assertAlmostEqual(row["lift_pp"], round(
                    row["hit_rate_pct"] - row["baseline_hit_rate_pct"], 2), places=2)
                self.assertGreaterEqual(row["hit_rate_pct"], 0)
                self.assertLessEqual(row["hit_rate_pct"], 100)
            if row["label"] == "uncertain":
                self.assertEqual(row["outcome"], "no_forecast")
                self.assertEqual(row["hit_rate_pct"], "")

    def test_range_requires_every_future_close_inside_frozen_bounds(self):
        closes = [100, 106, 102, 101, 100, 99]
        history = [{"ts": f"2026-01-{i + 1:02d} 12:00:00", "close": close}
                   for i, close in enumerate(closes)]
        labels = [{"label": "range" if i == 0 else "uncertain",
                   "support": 99, "resistance": 105} for i in range(len(history))]
        rows = forecast(history, labels, 2, "2026-01-04", "TEST", "1D", CONFIG)
        row = next(r for r in rows if r["sample"] == "train" and r["label"] == "range")
        self.assertEqual(row["observations"], 1)
        self.assertEqual(row["hit_rate_pct"], 0.0)
        self.assertEqual(row["outcome"], "all_next_closes_inside_frozen_range")


if __name__ == "__main__":
    unittest.main()
