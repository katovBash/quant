"""Predeclared pilot: EMA12/33 with past-only efficiency-ratio entry filter."""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.scan_ema import ema
from src.research.indicator_library import crosses
from src.research.monthly_efficiency import calendar_year_windows, efficiency_ratio, continuous_monthly_windows
from src.research.standalone_grid import UNIVERSE, load_bars
from src.ema.core.research_ema_combinations import simulate

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
OUT = HERE / "results"


def main() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    ticks = {item["SECID"]: float(item.get("MINSTEP") or 0) for item in universe}
    OUT.mkdir(exist_ok=True)
    rows = []
    month_rows = []
    year_rows = []
    monthly = {"protocol": str(PROTOCOL.relative_to(ROOT)),
               "snapshot": "2026-10-30", "history_status": "seen_history",
               "pairs": [], "errors": []}
    for symbol in protocol["symbols"]:
        try:
            bars = load_bars(symbol, "1H")
            closes = [bar["close"] for bar in bars]
            signals = crosses(ema(closes, 12), ema(closes, 33))
            settings = [("baseline", None, None, [True] * len(bars))]
            for length in protocol["lookbacks"]:
                values = efficiency_ratio(closes, length)
                for threshold in protocol["thresholds"]:
                    gate = [math.isfinite(value) and value >= threshold for value in values]
                    settings.append((f"er_{length}_{threshold:g}", length, threshold, gate))
            for name, length, threshold, gate in settings:
                curve, trades = [], []
                full = simulate(bars, signals, gate, gate, ticks[symbol], "2024-01-01",
                                equity_curve=curve, trade_log=trades)
                windows = continuous_monthly_windows(bars, curve, trades,
                                                     2024, protocol["split"])
                years = calendar_year_windows(bars, signals, gate, ticks[symbol], 2024)
                month_rows.extend({"symbol": symbol, "timeframe": "1H", "variant": name,
                                   **item} for item in windows["all"])
                year_rows.extend({"symbol": symbol, "timeframe": "1H", "variant": name,
                                  **item} for item in years)
                train = [item for item in windows["all"] if item["sample"] == "train"]
                late = [item for item in windows["all"] if item["sample"] != "train"]
                row = {"symbol": symbol, "timeframe": "1H", "variant": name,
                       "lookback": length or "", "threshold": threshold if threshold is not None else "",
                       "net_return_pct": full["return_pct"], "pnl_rub": full["pnl_rub"],
                       "closed_trades": full["closed_trades"],
                       "winning_trades": full["winning_trades"],
                       "profit_factor": full["profit_factor"],
                       "max_drawdown_pct": full["max_drawdown_pct"],
                       "months": windows["count"],
                       "nonpositive_months": windows["nonpositive_count"],
                       "worst_month_pct": windows["worst"]["return_pct"],
                       "median_month_pct": windows["median_return_pct"],
                       "zero_trade_months": windows["zero_trade_count"],
                       "train_nonpositive_months": sum(item["return_pct"] <= 0 for item in train),
                       "late_nonpositive_months": sum(item["return_pct"] <= 0 for item in late),
                       "late_months": len(late)}
                rows.append(row)
                monthly["pairs"].append({"symbol": symbol, "timeframe": "1H", "variant": name,
                                         "monthly_start_windows": {"1": windows},
                                         "calendar_years": years})
            print(symbol, "done", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            monthly["errors"].append({"symbol": symbol, "error": str(exc)})
            print(symbol, "ERROR", exc, flush=True)
    with (OUT / "all_variants.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    for filename, values in (("monthly_returns.csv", month_rows),
                             ("yearly_returns.csv", year_rows)):
        with (OUT / filename).open("w", newline="", encoding="utf-8") as stream:
            if values:
                writer = csv.DictWriter(stream, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
    (OUT / "monthly_validation.json").write_text(
        json.dumps(monthly, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    passing = [row for row in rows if row["months"] >= 12 and row["nonpositive_months"] == 0]
    by_variant = {}
    for name in sorted({row["variant"] for row in rows}):
        subset = [row for row in rows if row["variant"] == name]
        by_variant[name] = {"symbols": len(subset),
            "nonpositive_months": sum(row["nonpositive_months"] for row in subset),
            "train_nonpositive_months": sum(row["train_nonpositive_months"] for row in subset),
            "late_nonpositive_months": sum(row["late_nonpositive_months"] for row in subset),
            "worst_month_pct": min(row["worst_month_pct"] for row in subset),
            "median_full_return_pct": round(statistics.median(row["net_return_pct"] for row in subset), 2)}
    summary = {"pairs": len(rows), "strict_monthly_pass": len(passing),
               "decision": "NO_CANDIDATE" if not passing else "REVIEW_ONLY",
               "by_variant": by_variant, "errors": monthly["errors"]}
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
