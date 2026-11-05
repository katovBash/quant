"""Long-only and short-only diagnostics for selected combined-rule examples."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as combo

from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars


def main():
    output = HERE / "results"
    rows = list(csv.DictReader((output / "all_variants.csv").open()))
    monthly_rows = list(csv.DictReader((output / "monthly_returns.csv").open()))
    candidates = []
    for timeframe in combo.PROTOCOL["signal_timeframes"]:
        available = [row for row in rows if row["timeframe"] == timeframe and
                     row["variant"] == "turtle_entry_ema_higher"]
        available.sort(key=lambda row: (int(row["positive_months"]),
                                        float(row["worst_month_pnl_rub"]),
                                        float(row["net_return_pct"])), reverse=True)
        candidates.extend(available[:5])
    side_rows = []
    side_monthly = []
    for candidate in candidates:
        symbol, timeframe, variant = (candidate[key] for key in ("symbol", "timeframe", "variant"))
        bars = load_research_bars(combo.CACHE, symbol, timeframe)
        entries, exits, gate_up, gate_down = combo.variants_for(symbol, timeframe, bars)[variant]
        for mode in ("long_only", "short_only"):
            up = gate_up if mode == "long_only" else [False] * len(bars)
            down = gate_down if mode == "short_only" else [False] * len(bars)
            curve, trades = [], []
            result = simulate(bars, entries, up, down, 0.0, combo.PROTOCOL["start"],
                              fee_bps=combo.PROTOCOL["simulator_cost_bps_per_side"],
                              equity_curve=curve, trade_log=trades, exit_signals=exits)
            observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= combo.PROTOCOL["start"]}
            months = [item for item in continuous_monthly_windows(
                bars, curve, trades, 2024, combo.PROTOCOL["split"])["all"]
                if item["start"][:7] in observed]
            side_monthly.extend({"symbol": symbol, "timeframe": timeframe,
                                 "variant": variant, "mode": mode, **item}
                                for item in months)
            long_trades = [trade for trade in trades if trade["side"] == "long"]
            short_trades = [trade for trade in trades if trade["side"] == "short"]
            side_rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                              "mode": mode, "long_closed": len(long_trades),
                              "long_wins": sum(trade["pnl_rub"] > 0 for trade in long_trades),
                              "short_closed": len(short_trades),
                              "short_wins": sum(trade["pnl_rub"] > 0 for trade in short_trades),
                              "return_pct": result["return_pct"],
                              "profitable_months": sum(item["pnl_rub"] > 0 for item in months),
                              "months": len(months),
                              "conclusion": "diagnostic_only; compare monthly downside and both directions"})
    combo.write_csv(output / "trade_side_summary.csv", side_rows,
                    ("symbol", "timeframe", "variant", "mode", "long_closed", "long_wins",
                     "short_closed", "short_wins", "return_pct", "profitable_months", "months",
                     "conclusion"))
    combo.write_csv(output / "trade_side_monthly.csv", side_monthly)
    summary = json.loads((output / "summary.json").read_text())
    build_report(output, combo.PROTOCOL, summary, rows, monthly_rows)
    print(f"{len(side_rows)} directional diagnostics saved")


if __name__ == "__main__":
    main()
