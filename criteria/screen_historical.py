"""Screen historical rows for paper-trading review, never for proof of an edge."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def screen(row: dict, baseline: dict | None = None, *, min_trades: int = 1,
           min_late_trades: int = 0, min_pf: float = 1.2,
           max_drawdown_pct: float = 20.0) -> list[str]:
    lab = "full_closed_trades" in row
    field = (lambda simple, combo: combo if lab else simple)

    def value(*names: str) -> str:
        for name in names:
            if name in row and row[name] != "":
                return row[name]
        raise KeyError(f"missing metric: {names}")
    failures = []
    if int(value(field("closed_trades", "full_closed_trades"))) < min_trades:
        failures.append("too_few_total_trades")
    late_trades = value("late_closed_trades") if lab else value("oos_trades", "late_trades")
    if int(late_trades) < min_late_trades:
        failures.append("too_few_late_trades")
    if float(value(field("net_return_pct", "full_return_pct"))) <= 0:
        failures.append("nonpositive_total_return")
    late_return = value("late_return_pct") if lab else value("oos_return_pct", "late_return_pct")
    if float(late_return) <= 0:
        failures.append("nonpositive_late_return")
    if float(value(field("profit_factor", "full_profit_factor"))) <= min_pf:
        failures.append("low_profit_factor")
    # Legacy scans use a signed loss, while the new EMA grid stores depth as positive.
    if abs(float(value(field("max_drawdown_pct", "full_max_drawdown_pct")))) > max_drawdown_pct:
        failures.append("drawdown_too_deep")
    if lab and baseline is not None and row.get("variant") != "baseline":
        if float(row["train_return_pct"]) <= float(baseline["train_return_pct"]):
            failures.append("no_early_improvement_over_base")
        if float(row["late_return_pct"]) <= float(baseline["late_return_pct"]):
            failures.append("no_late_improvement_over_base")
    elif not lab and "oos_excess_pp" in row and float(row["oos_excess_pp"]) <= 0:
        failures.append("no_late_excess_over_buy_hold")
    return failures


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--timeframe")
    p.add_argument("--symbol")
    p.add_argument("--fast", type=int)
    p.add_argument("--slow", type=int)
    p.add_argument("--mode")
    p.add_argument("--variant")
    p.add_argument("--min-trades", type=int, default=1)
    p.add_argument("--min-late-trades", type=int, default=0)
    p.add_argument("--min-pf", type=float, default=1.2)
    p.add_argument("--max-drawdown-pct", type=float, default=20.0)
    args = p.parse_args()
    with args.input.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    baselines = {(r["symbol"], r["timeframe"]): r for r in rows if r.get("variant") == "baseline"}
    selected = []
    total = 0
    for r in rows:
        if any(value is not None and str(r.get(key)) != str(value) for key, value in (
            ("timeframe", args.timeframe), ("symbol", args.symbol),
            ("fast", args.fast), ("slow", args.slow),
            ("mode", args.mode), ("variant", args.variant),
        )):
            continue
        total += 1
        base = baselines.get((r["symbol"], r["timeframe"]))
        failures = screen(r, base, min_trades=args.min_trades,
                          min_late_trades=args.min_late_trades,
                          min_pf=args.min_pf, max_drawdown_pct=args.max_drawdown_pct)
        if not failures:
            selected.append({"symbol": r["symbol"], "timeframe": r["timeframe"],
                             "mode": r.get("mode"), "variant": r.get("variant"),
                             "closed_trades": int(r.get("closed_trades", r.get("full_closed_trades"))),
                             "late_closed_trades": int(r.get("oos_trades", r.get("late_trades", r.get("late_closed_trades")))),
                             "late_return_pct": float(r.get("oos_return_pct", r.get("late_return_pct")))})
    selected.sort(key=lambda x: x["late_return_pct"], reverse=True)
    print(json.dumps({"status": "HISTORICAL_SCREEN_ONLY", "tested_rows": total,
                      "passed_rows": len(selected), "candidates": selected,
                      "note": "Passing is eligibility for paper review, not a probability of being nonrandom"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
