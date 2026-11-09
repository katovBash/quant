"""Recalculate long-only and short-only diagnostics for the full fixed grid."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars
from src.research.trader_method_run import write_csv
from run import signals

EXPERIMENT = Path(__file__).resolve().parent
RESULTS = EXPERIMENT / "results"
FIELDS = ("symbol", "timeframe", "variant", "mode", "long_closed", "long_wins",
          "short_closed", "short_wins", "return_pct", "profitable_months",
          "months", "conclusion")


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    protocol = json.loads((EXPERIMENT / "protocol.json").read_text(encoding="utf-8"))
    all_rows = read_csv(RESULTS / "all_variants.csv")
    by_symbol = defaultdict(list)
    for row in all_rows:
        if row["variant"] != "baseline":
            by_symbol[row["symbol"]].append(row["variant"])
    rows = []
    for number, (symbol, variants) in enumerate(sorted(by_symbol.items()), 1):
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, "1D")
        for variant in variants:
            entries, exits = signals(variant, bars)
            for mode in ("long_only", "short_only"):
                up = [mode == "long_only"] * len(bars)
                down = [mode == "short_only"] * len(bars)
                curve, trades = [], []
                outcome = simulate(
                    bars, entries, up, down, 0.0, protocol["start"],
                    fee_bps=protocol["simulator_cost_bps_per_side"],
                    equity_curve=curve, trade_log=trades, exit_signals=exits)
                months = continuous_monthly_windows(
                    bars, curve, trades, 2024, protocol["split"])["all"]
                rows.append({"symbol": symbol, "timeframe": "1D", "variant": variant,
                             "mode": mode,
                             "long_closed": sum(t["side"] == "long" for t in trades),
                             "long_wins": sum(t["side"] == "long" and t["pnl_rub"] > 0 for t in trades),
                             "short_closed": sum(t["side"] == "short" for t in trades),
                             "short_wins": sum(t["side"] == "short" and t["pnl_rub"] > 0 for t in trades),
                             "return_pct": outcome["return_pct"],
                             "profitable_months": sum(m["pnl_rub"] > 0 for m in months),
                             "months": len(months),
                             "conclusion": "diagnostic_only; full declared grid"})
        if number % 50 == 0 or number == len(by_symbol):
            print(f"side analysis: {number}/{len(by_symbol)} symbols", flush=True)
    write_csv(RESULTS / "trade_side_summary.csv", rows, FIELDS)
    summary = json.loads((RESULTS / "summary.json").read_text(encoding="utf-8"))
    monthly = read_csv(RESULTS / "monthly_returns.csv")
    build_report(RESULTS, protocol, summary, all_rows, monthly)


if __name__ == "__main__":
    main()
