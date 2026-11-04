import unittest
from unittest.mock import patch

from src.ema.core.quant import Bar, EMA_PERIODS, buy_hold_baseline, indicators, run


def bars(prices):
    from datetime import date, timedelta
    first = date(2020, 1, 1)
    days = []
    current = first
    while len(days) < len(prices):
        if current.weekday() < 5:
            days.append(str(current))
        current += timedelta(days=1)
    return [Bar(day, p, p + 1, p - 1, p, 1000) for day, p in zip(days, prices)]


class StrategyTests(unittest.TestCase):
    def test_exact_ema_periods_and_warmup(self):
        self.assertEqual(EMA_PERIODS, (12, 33, 66))
        output = indicators(bars([100 + i * 0.01 for i in range(70)]), mode="cross12_33")
        self.assertEqual(set(output[65]["ema"]), {12, 33, 66})
        self.assertFalse(output[64]["ready"])
        self.assertTrue(output[65]["ready"])
        self.assertFalse(output[64]["enter"])

    def test_flat_series_has_no_trades(self):
        data = {s: bars([100] * 80) for s in ("GAZP", "VTBR")}
        result = run(data, fee_bps=0, slippage_bps=0)
        self.assertEqual(result["trades"], [])
        self.assertEqual(result["final_rub"], 1_000_000)
        self.assertEqual(result["next_session"]["GAZP"]["signal"], "WAIT")

    def test_close_signal_executes_at_next_open(self):
        data = {s: bars([100] * 68) for s in ("GAZP", "VTBR")}
        fake = [{"ema": {12: 100, 33: 99, 66: 98}, "weekly_ema": {33: 100, 66: 99},
                 "atr": 1, "ready": i >= 65,
                 "enter": i == 66, "exit": False} for i in range(68)]
        with patch("src.ema.core.quant.indicators", return_value=fake):
            result = run(data)
        buys = [t for t in result["trades"] if t["side"] == "BUY"]
        self.assertEqual(len(buys), 2)
        self.assertTrue(all(t["date"] == data["GAZP"][67].day for t in buys))
        self.assertLess(result["final_rub"], result["initial_rub"])

    def test_current_week_does_not_see_friday_close(self):
        original = bars([100 + i * 0.01 for i in range(680)])
        changed = list(original)
        from datetime import date
        friday = max(i for i, b in enumerate(changed) if date.fromisoformat(b.day).weekday() == 4)
        changed[friday] = Bar(changed[friday].day, 500, 501, 499, 500, 1000)
        monday = friday - 4
        self.assertEqual(indicators(original)[monday]["weekly_ema"], indicators(changed)[monday]["weekly_ema"])

    def test_ema33_touch_and_rebound_generates_entry(self):
        data = bars([100 + i * 0.1 for i in range(700)])
        prior = data[-2]
        data[-2] = Bar(prior.day, prior.open - 0.7, prior.high - 0.7,
                       prior.low - 0.7, prior.close - 0.7, prior.volume)
        current = data[-1]
        data[-1] = Bar(current.day, current.open - 0.5, current.high,
                       current.close - 2.1, current.close, current.volume)
        result = indicators(data, mode="support", support_line=33)
        self.assertTrue(result[-1]["enter"])
        self.assertGreater(result[-1]["weekly_ema"][33], result[-1]["weekly_ema"][66])

    def test_cross_modes_are_distinct(self):
        def series(down_days):
            prices = [100 + i * 0.2 for i in range(100)]
            peak = prices[-1]
            prices += [peak - 0.2 * (i + 1) for i in range(down_days)]
            trough = prices[-1]
            prices += [trough + 0.4 * (i + 1) for i in range(25)]
            return bars(prices)

        fast = indicators(series(20), mode="cross12_33")
        slow = indicators(series(20), mode="cross33_66")
        self.assertTrue(any(x["enter"] for x in fast))
        self.assertFalse(any(x["enter"] for x in slow))
        self.assertTrue(any(x["enter"] for x in indicators(series(40), mode="cross33_66")))

    def test_pure_vtbr_cross_opens_and_closes_without_stop(self):
        prices = [100 - i * 0.1 for i in range(70)]
        prices += [93 + i * 0.4 for i in range(20)]
        prices += [101 - i * 0.5 for i in range(30)]
        result = run({"VTBR": bars(prices)}, mode="cross12_33_pure",
                     fee_bps=0, slippage_bps=0)
        self.assertEqual([t["side"] for t in result["trades"]], ["BUY", "SELL"])
        self.assertEqual({t["reason"] for t in result["trades"]}, {"cross12_33_pure", "trend"})
        self.assertEqual(result["next_session"]["VTBR"]["stop"], None)
        self.assertNotIn("GAZP", result["next_session"])

    def test_buy_hold_baseline_uses_same_position_cap(self):
        data = bars([100] * 70)
        result = buy_hold_baseline(data, data[0].day, 1000, 0, 0, 1)
        self.assertEqual(result["entries"], 1)
        self.assertEqual(result["final_rub"], 1000)


if __name__ == "__main__":
    unittest.main()
