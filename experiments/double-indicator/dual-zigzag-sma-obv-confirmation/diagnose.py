"""Recompute selected-stock trade directions and parent entries removed by OBV confirmation."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
spec = importlib.util.spec_from_file_location("atr_experiment", HERE / "run.py")
if spec is None or spec.loader is None:
    raise RuntimeError("experiment runner unavailable")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parent_review = json.loads((ROOT / "experiments/double-indicator/dual-zigzag-daily-trend/results/paper_review.json").read_text())
    symbols = [item["symbol"] for item in parent_review["stocks"]]
    side_rows, removed_rows = [], []
    for symbol in symbols:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, "4H")
        factory = experiment.factory(symbol, "4H")
        source = {}
        for variant in ("parent", "obv_5", "obv_10", "obv_20", "combined_5", "combined_10", "combined_20"):
            entries, exits = factory(variant, bars)
            all_trades = []
            for mode, up, down in (("long_short", True, True),
                                   ("long_only", True, False),
                                   ("short_only", False, True)):
                trades = all_trades if mode == "long_short" else []
                curve = []
                result = simulate(bars, entries, [up] * len(bars), [down] * len(bars),
                                  0.0, "2024-01-01", fee_bps=15,
                                  equity_curve=curve, trade_log=trades, exit_signals=exits)
                months = continuous_monthly_windows(bars, curve, trades, 2024, "2026-01-01")["all"]
                side_rows.append({"symbol": symbol, "timeframe": "4H",
                                  "variant": variant, "mode": mode,
                                  "long_closed": sum(t["side"] == "long" for t in trades),
                                  "long_wins": sum(t["side"] == "long" and t["pnl_rub"] > 0 for t in trades),
                                  "short_closed": sum(t["side"] == "short" for t in trades),
                                  "short_wins": sum(t["side"] == "short" and t["pnl_rub"] > 0 for t in trades),
                                  "return_pct": result["return_pct"],
                                  "profitable_months": sum(item["pnl_rub"] > 0 for item in months),
                                  "months": len(months),
                                  "conclusion": "selected stocks only; compare PnL and risk",
                                  "closed_loss_pnl_rub": round(sum(t["pnl_rub"] for t in trades if t["pnl_rub"] < 0), 2),
                                  "closed_win_pnl_rub": round(sum(t["pnl_rub"] for t in trades if t["pnl_rub"] > 0), 2)})
            source[variant] = all_trades
        parent_trades = source["parent"]
        keys = [(t["entry_date"], t["side"]) for t in parent_trades]
        if len(keys) != len(set(keys)):
            raise ValueError(f"ambiguous same-day parent entries: {symbol}")
        for variant in ("combined_5", "combined_10", "combined_20"):
            retained = Counter((t["entry_date"], t["side"]) for t in source[variant])
            for trade in parent_trades:
                key = trade["entry_date"], trade["side"]
                if retained[key]:
                    retained[key] -= 1
                    continue
                removed_rows.append({"symbol": symbol, "timeframe": "4H",
                                     "variant": variant,
                                     "parent_entry_date": trade["entry_date"],
                                     "parent_exit_date": trade["exit_date"],
                                     "side": trade["side"],
                                     "parent_outcome": "win" if trade["pnl_rub"] > 0 else
                                     "loss" if trade["pnl_rub"] < 0 else "zero",
                                     "parent_trade_pnl_rub": trade["pnl_rub"]})
    write(RESULTS / "trade_side_summary.csv", side_rows, list(side_rows[0]))
    write(RESULTS / "removed_parent_trades.csv", removed_rows,
          ["symbol", "timeframe", "variant", "parent_entry_date",
           "parent_exit_date", "side", "parent_outcome", "parent_trade_pnl_rub"])
    print(json.dumps({"selected_symbols": len(symbols), "side_rows": len(side_rows),
                      "removed_parent_trades": len(removed_rows)}))


if __name__ == "__main__":
    main()
