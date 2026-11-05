import math
import unittest

from src.research.standalone_grid import (
    crossing, pattern_signals, ema_level_signals, variants, evaluate, buy_hold_return,
)
from src.ema.core.research_ema_combinations import simulate


def bars(count=120):
    result = []
    for i in range(count):
        price = 100 + 8 * math.sin(i / 4)
        result.append({"ts": f"2024-01-{1 + i // 24:02d} {i % 24:02d}:00:00",
                       "open": price - 0.5, "high": price + 1.5,
                       "low": price - 1.5, "close": price + 0.5,
                       "volume": 1000})
    return result


class StandaloneGridTests(unittest.TestCase):
    def test_rsi_threshold_crossing(self):
        self.assertEqual(crossing([math.nan, 40, 49, 51, 60, 49], 50, 50),
                         [0, 0, 0, 1, 0, -1])

    def test_breakout_uses_previous_bars_only(self):
        sample = bars(50)
        for bar in sample:
            bar.update(open=100, high=101, low=99, close=100)
        sample[25].update(high=110, close=109)
        signals = pattern_signals(sample, "breakout", 10)
        self.assertEqual(signals[25], 1)
        self.assertEqual(signals[26], 0)

    def test_ema_as_support_and_resistance_without_crossing_second_ema(self):
        sample = bars(80)
        for bar in sample:
            bar.update(open=100, high=101, low=99, close=100)
        sample[70].update(open=100, high=102, low=99.5, close=101)
        sample[71].update(open=100, high=102, low=99.5, close=101)
        sample[72].update(open=100, high=100.5, low=98, close=99)
        signals = ema_level_signals(sample, 12, 1.0)
        self.assertEqual(signals[70], 1)
        self.assertEqual(signals[72], -1)
        self.assertEqual(signals[:70], [0] * 70)

    def test_ema_zone_rejects_deep_break_and_changes_with_width(self):
        sample = bars(80)
        for bar in sample:
            bar.update(open=100, high=100.5, low=99.5, close=100)
        sample[70].update(high=101, low=96, close=101)
        sample[72].update(high=101, low=99.3, close=101)
        tight = ema_level_signals(sample, 12, 0.25)
        wide = ema_level_signals(sample, 12, 1.0)
        self.assertEqual(tight[70], 0)
        self.assertEqual(wide[70], 0)
        self.assertEqual(tight[72], 0)
        self.assertEqual(wide[72], 1)

    def test_all_indicators_ignore_appended_future_bar(self):
        original = bars()
        extra = {"ts": "2024-01-06 00:00:00", "open": 100, "high": 400,
                 "low": 1, "close": 300, "volume": 10000}
        for family in ("rsi", "adx", "four_point_levels", "patterns", "ema_levels"):
            before = {name: signal for name, _, signal in variants(family, original)}
            after = {name: signal for name, _, signal in variants(family, original + [extra])}
            self.assertEqual(before.keys(), after.keys())
            for name in before:
                self.assertEqual(before[name], after[name][:len(original)], (family, name))

    def test_output_has_all_direction_modes_and_hold_control(self):
        sample = bars()
        rows = evaluate("rsi", "TEST", "1H", sample, 0.01)
        self.assertEqual(len(rows), 3 * 3 * 3)
        self.assertEqual({row["mode"] for row in rows}, {"long", "short", "long_short"})
        self.assertEqual(rows[0]["buy_hold_return_pct"],
                         buy_hold_return(sample, "2024-01-01", 0.01))

    def test_signal_fills_at_next_open_with_costs(self):
        sample = bars(60)
        for i, bar in enumerate(sample):
            price = 200 if 41 <= i <= 45 else 100
            bar.update(open=price, high=price + 1, low=price - 1, close=price)
        signals = [0] * len(sample)
        signals[40], signals[45] = 1, -1
        result = simulate(sample, signals, [True] * len(sample),
                          [False] * len(sample), 0.01, "2024-01-01")
        self.assertEqual(result["closed_trades"], 1)
        self.assertLess(result["return_pct"], -24)
        trades = []
        traced = simulate(sample, signals, [True] * len(sample),
                          [False] * len(sample), 0.01, "2024-01-01", trade_log=trades)
        self.assertEqual(traced, result)
        self.assertEqual(len(trades), 1)
        self.assertLess(trades[0]["pnl_rub"], 0)

    def test_equity_trace_preserves_backtest_result(self):
        sample = bars(60)
        signals = [0] * len(sample)
        signals[40] = 1
        allowed = [True] * len(sample)
        baseline = simulate(sample, signals, allowed, allowed, 0.01, "2024-01-01")
        curve = []
        traced = simulate(sample, signals, allowed, allowed, 0.01, "2024-01-01",
                          equity_curve=curve)
        self.assertEqual(traced, baseline)
        self.assertEqual(traced["return_pct"],
                         round(100 * (curve[-1]["equity"] / 1_000_000 - 1), 2))
        self.assertEqual(len(curve), len(sample) - 33)

    def test_exit_signal_closes_without_new_entry(self):
        sample = bars(60)
        entries = [0] * len(sample)
        exits = [0] * len(sample)
        entries[40] = 1
        exits[45] = -1
        trace = []
        result = simulate(sample, entries, [True] * len(sample), [True] * len(sample),
                          0.01, "2024-01-01", exit_signals=exits, trade_log=trace)
        self.assertEqual(result["closed_trades"], 1)
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["side"], "long")

    def test_ex_date_cash_flow_offsets_short_gap(self):
        sample = []
        for index in range(40):
            price = 80 if index >= 35 else 100
            sample.append({"ts": f"2024-01-{1 if index < 35 else 2:02d} {index % 24:02d}:00:00",
                           "open": price, "high": price, "low": price, "close": price})
        events = [0] * len(sample)
        events[33] = -1
        allowed = [True] * len(sample)
        without = simulate(sample, events, allowed, allowed, 0, "2024-01-01", fee_bps=0)
        with_dividend = simulate(sample, events, allowed, allowed, 0, "2024-01-01",
                                 fee_bps=0, dividends_per_share={"2024-01-02": 20})
        self.assertEqual(without["return_pct"], 5.0)
        self.assertEqual(with_dividend["return_pct"], 0.0)
        self.assertEqual(with_dividend["closed_trades"], 0)


if __name__ == "__main__":
    unittest.main()
