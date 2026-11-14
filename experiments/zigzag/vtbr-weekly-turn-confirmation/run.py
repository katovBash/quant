"""Single-symbol diagnostic of causal weekly Band-ZigZag entry confirmations."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.band_zigzag_weekly import band_events, signals_for_variant
from src.research.trader_method_run import run
from src.research.timeframes import load_research_bars
from src.ema.core.research_ema_combinations import simulate
from src.research.monthly_efficiency import continuous_monthly_windows
import csv
import json


def signals(variant: str, bars: list[dict]):
    if variant == "directional_2":
        return signals_for_variant("bb20__two_closes__opposite", bars)
    mode, count_text = variant.rsplit("_", 1)
    count = int(count_text)
    events = band_events(bars)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    side = 0
    pivot = -1
    extreme = 0.0
    used = -1
    closes = [float(bar["close"]) for bar in bars]
    for i, bar in enumerate(bars):
        high_event, low_event = events[i]
        if high_event != low_event:
            new_side = 1 if high_event else -1
            price = float(bar["high"] if new_side == 1 else bar["low"])
            if side != new_side or (new_side == 1 and price > extreme) or (new_side == -1 and price < extreme):
                side, pivot, extreme = new_side, i, price
        if i < max(20, count + 18) or side == 0 or not 0 < i - pivot <= 8 or used == pivot:
            continue
        # All comparisons use completed weekly closes available at signal time.
        directional = all((closes[j] > closes[j - 1]) if side == -1 else
                          (closes[j] < closes[j - 1]) for j in range(i - count + 1, i + 1))
        above_mean = all((closes[j] > sum(closes[j - 19:j + 1]) / 20) if side == -1 else
                         (closes[j] < sum(closes[j - 19:j + 1]) / 20)
                         for j in range(i - count + 1, i + 1))
        confirmed = ((directional if mode == "directional" else
                      above_mean if mode == "sma20" else directional and above_mean))
        if confirmed:
            entries[i] = 1 if side == -1 else -1
            used = pivot
    return entries, exits


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    run(experiment, signal_factory=signals)
    protocol = json.loads((experiment / "protocol.json").read_text())
    bars = load_research_bars(ROOT / "data/candles/moex_scan", "VTBR", "1W")
    sides = []
    side_months = []
    for variant in protocol["expected_variants"]:
        if variant == "baseline":
            continue
        entries, exits = signals(variant, bars)
        for side in ("long_only", "short_only"):
            selected = [value if (value > 0 if side == "long_only" else value < 0) else 0
                        for value in entries]
            curve, trades = [], []
            result = simulate(bars, selected, [True] * len(bars), [True] * len(bars),
                              0.0, protocol["start"], fee_bps=protocol["simulator_cost_bps_per_side"],
                              equity_curve=curve, trade_log=trades, exit_signals=entries)
            months = continuous_monthly_windows(bars, curve, trades, 2024, protocol["split"])["all"]
            sides.append({"variant": variant, "side": side, "return_pct": result["return_pct"],
                          "closed_trades": result["closed_trades"], "winning_trades": result["winning_trades"],
                          "max_drawdown_pct": result["max_drawdown_pct"],
                          "positive_months": sum(row["pnl_rub"] > 0 for row in months),
                          "worst_month_pnl_rub": min(row["pnl_rub"] for row in months)})
            side_months.extend({"variant": variant, "side": side, **row} for row in months)
    for name, rows in (("direction_summary.csv", sides), ("monthly_side_returns.csv", side_months)):
        with (experiment / "results" / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
