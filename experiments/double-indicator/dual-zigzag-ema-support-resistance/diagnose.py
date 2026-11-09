"""Compare leading EMA confirmations with the original eight SMA20 paper stocks."""

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

SOURCE = Path(__file__).with_name("run.py")
spec = importlib.util.spec_from_file_location("ema_support_diagnostic", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("experiment runner unavailable")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

VARIANTS = ("zz_sma20", "sma20_same_20_recent5", "sma20_same_9_recent5")
SYMBOLS = [item["symbol"] for item in json.loads((ROOT /
           "strategies/dual-zigzag-daily-sma20-4h/selection.json").read_text())["top10"]]
OUT = Path(__file__).with_name("results")


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    side_rows, removed_rows = [], []
    for symbol in SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, "4H")
        factory = module.factory(symbol, "4H")
        signals = {variant: factory(variant, bars) for variant in VARIANTS}
        histories = {}
        for variant, (entries, exits) in signals.items():
            for mode in ("all", "long_only", "short_only"):
                up = [mode != "short_only"] * len(bars)
                down = [mode != "long_only"] * len(bars)
                curve, trades = [], []
                result = simulate(bars, entries, up, down, 0.0, "2024-01-01",
                                  fee_bps=15, equity_curve=curve, trade_log=trades,
                                  exit_signals=exits)
                months = continuous_monthly_windows(bars, curve, trades,
                                                     2024, "2026-01-01")["all"]
                long = [trade for trade in trades if trade["side"] == "long"]
                short = [trade for trade in trades if trade["side"] == "short"]
                side_rows.append({"symbol": symbol, "timeframe": "4H", "variant": variant,
                                  "mode": mode, "long_closed": len(long),
                                  "long_wins": sum(t["pnl_rub"] > 0 for t in long),
                                  "short_closed": len(short),
                                  "short_wins": sum(t["pnl_rub"] > 0 for t in short),
                                  "return_pct": result["return_pct"],
                                  "profitable_months": sum(m["pnl_rub"] > 0 for m in months),
                                  "months": len(months),
                                  "conclusion": "original eight SMA20 stocks; seen history"})
                if mode == "all":
                    histories[variant] = trades
        parent = histories["zz_sma20"]
        for variant in VARIANTS[1:]:
            other = histories[variant]
            other_keys = Counter((t["entry_date"], t["side"]) for t in other)
            removed = []
            for trade in parent:
                key = (trade["entry_date"], trade["side"])
                if other_keys[key]:
                    other_keys[key] -= 1
                else:
                    removed.append(trade)
            original, accepted = signals["zz_sma20"][0], signals[variant][0]
            removed_rows.append({"symbol": symbol, "timeframe": "4H", "variant": variant,
                                 "parent_entry_events": sum(bool(x) for x in original),
                                 "accepted_entry_events": sum(bool(x) for x in accepted),
                                 "removed_entry_events": sum(bool(x) and not accepted[i]
                                                             for i, x in enumerate(original)),
                                 "removed_parent_closed_trades": len(removed),
                                 "removed_losing_trades": sum(t["pnl_rub"] <= 0 for t in removed),
                                 "removed_winning_trades": sum(t["pnl_rub"] > 0 for t in removed),
                                 "candidate_only_closed_trades": sum(other_keys.values())})
    _write(OUT / "trade_side_summary.csv", side_rows, list(side_rows[0]))
    _write(OUT / "removed_parent_trades.csv", removed_rows, list(removed_rows[0]))
    print("wrote", len(side_rows), "side rows and", len(removed_rows), "removal rows")


if __name__ == "__main__":
    main()
