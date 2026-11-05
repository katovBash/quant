"""Direction diagnostics for the selected Fibonacci rule and matched 0.618."""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars
from src.research.trader_method_run import write_csv
from src.research.fibonacci_signals import retracement_signals
from src.research.experiment_report import build_report


def main() -> None:
    output = HERE / "results"
    protocol = json.loads((HERE / "protocol.json").read_text())
    review = json.loads((output / "paper_review.json").read_text())
    selected = review["rule"]["variant"]
    parts = selected.split("_")
    variants = [selected, f"fib_{parts[1]}_0.618_{parts[3]}"]
    side_rows, monthly = [], []
    for stock in review["stocks"]:
        symbol = stock["symbol"]
        bars = load_research_bars(ROOT / protocol["eligible_universe"]["cache_dir"],
                                  symbol, review["rule"]["timeframe"])
        observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= protocol["start"]}
        for variant in variants:
            _, wing, ratio, tolerance = variant.split("_")
            entries, exits = retracement_signals(bars, int(wing), float(ratio), float(tolerance))
            for mode in ("long_only", "short_only"):
                up = [mode == "long_only"] * len(bars)
                down = [mode == "short_only"] * len(bars)
                curve, trades = [], []
                result = simulate(bars, entries, up, down, 0.0, protocol["start"],
                                  fee_bps=protocol["simulator_cost_bps_per_side"],
                                  equity_curve=curve, trade_log=trades, exit_signals=exits)
                months = [item for item in continuous_monthly_windows(
                    bars, curve, trades, 2024, protocol["split"])["all"]
                    if item["start"][:7] in observed]
                monthly.extend({"symbol": symbol, "timeframe": review["rule"]["timeframe"],
                                "variant": variant, "mode": mode, **item} for item in months)
                longs = [trade for trade in trades if trade["side"] == "long"]
                shorts = [trade for trade in trades if trade["side"] == "short"]
                side_rows.append({"symbol": symbol, "timeframe": review["rule"]["timeframe"],
                                  "variant": variant, "mode": mode,
                                  "long_closed": len(longs),
                                  "long_wins": sum(trade["pnl_rub"] > 0 for trade in longs),
                                  "short_closed": len(shorts),
                                  "short_wins": sum(trade["pnl_rub"] > 0 for trade in shorts),
                                  "return_pct": result["return_pct"],
                                  "profitable_months": sum(item["pnl_rub"] > 0 for item in months),
                                  "months": len(months),
                                  "conclusion": "diagnostic_only; compare yearly and monthly downside"})
    write_csv(output / "trade_side_summary.csv", side_rows)
    write_csv(output / "trade_side_monthly.csv", monthly)
    with (output / "all_variants.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with (output / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        months = list(csv.DictReader(stream))
    build_report(output, protocol, json.loads((output / "summary.json").read_text()), rows, months)
    print(f"{len(side_rows)} directional cases")


if __name__ == "__main__":
    main()
