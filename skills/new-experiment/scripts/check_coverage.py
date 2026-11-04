"""Check full experiment CSV coverage without reading performance as selection input."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def period_coverage(path: Path, expected: set[tuple[str, str, str]],
                    period_field: str, min_periods: int) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    needed = {"symbol", "timeframe", "variant", period_field, "return_pct", "closed_trades"}
    if not rows or not needed <= set(rows[0]):
        raise ValueError(f"{path} needs {sorted(needed)}")
    periods: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    duplicates = []
    for row in rows:
        key = (row["symbol"], row["timeframe"], row["variant"])
        period = row[period_field]
        if period in periods[key]:
            duplicates.append([*key, period])
        periods[key].add(period)
    short = {"/".join(key): len(periods.get(key, set())) for key in expected
             if len(periods.get(key, set())) < min_periods}
    return {"rows": len(rows), "pairs": len(periods), "missing_or_short": short,
            "duplicates": duplicates,
            "min_periods_available": min((len(periods.get(key, set())) for key in expected), default=0),
            "ok": not short and not duplicates and set(periods) == expected}


def check(path: Path, frames: list[str], minimum: int,
          monthly: Path | None = None, yearly: Path | None = None,
          trade_windows_path: Path | None = None) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = {"symbol", "timeframe", "variant", "closed_trades"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("CSV needs nonempty symbol,timeframe,variant,closed_trades columns")
    variants = {row["variant"] for row in rows}
    grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    expected: set[tuple[str, str, str]] = set()
    duplicates = []
    trades = {}
    for row in rows:
        symbol, frame, variant = (row[key] for key in ("symbol", "timeframe", "variant"))
        if not symbol or not frame or not variant:
            raise ValueError("empty symbol/timeframe/variant")
        if variant in grouped[frame][symbol]:
            duplicates.append([symbol, frame, variant])
        grouped[frame][symbol].add(variant)
        key = (symbol, frame, variant)
        expected.add(key)
        trades[key] = int(row["closed_trades"])
    details = {}
    for frame in frames:
        symbols = grouped.get(frame, {})
        incomplete = {symbol: sorted(variants - observed)
                      for symbol, observed in symbols.items() if observed != variants}
        details[frame] = {"symbols": len(symbols), "min_required": minimum,
                          "variants": len(variants), "incomplete_symbols": incomplete,
                          "ok": len(symbols) >= minimum and not incomplete}
    result = {"ok": all(item["ok"] for item in details.values()) and not duplicates,
              "rows": len(rows), "duplicates": duplicates, "timeframes": details,
              "pairs_with_at_least_100_closed_trades": sum(value >= 100 for value in trades.values()),
              "pairs_below_100_closed_trades": sum(value < 100 for value in trades.values())}
    if monthly is not None:
        result["monthly"] = period_coverage(monthly, expected, "start", 1)
        result["ok"] = result["ok"] and result["monthly"]["ok"]
    if yearly is not None:
        result["yearly"] = period_coverage(yearly, expected, "year", 1)
        result["ok"] = result["ok"] and result["yearly"]["ok"]
    if trade_windows_path is not None:
        with trade_windows_path.open(newline="", encoding="utf-8-sig") as stream:
            window_rows = list(csv.DictReader(stream))
        window_counts: dict[tuple[str, str, str], int] = defaultdict(int)
        invalid = 0
        for row in window_rows:
            key = (row["symbol"], row["timeframe"], row["variant"])
            window_counts[key] += 1
            invalid += (key not in expected or int(row["closed_trades"]) != 100
                        or int(row["last_trade_number"]) - int(row["first_trade_number"]) != 99)
        missing = {"/".join(key): {"expected": max(0, count - 99),
                                  "actual": window_counts.get(key, 0)}
                   for key, count in trades.items()
                   if window_counts.get(key, 0) != max(0, count - 99)}
        result["trade_windows_100"] = {"rows": len(window_rows), "invalid": invalid,
                                       "missing_or_extra": missing,
                                       "ok": invalid == 0 and not missing}
        result["ok"] = result["ok"] and result["trade_windows_100"]["ok"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--timeframes", nargs="+", required=True)
    parser.add_argument("--min-symbols", type=int, default=100)
    parser.add_argument("--monthly-csv", type=Path, required=True)
    parser.add_argument("--yearly-csv", type=Path)
    parser.add_argument("--trade-windows-csv", type=Path)
    args = parser.parse_args()
    result = check(args.csv, args.timeframes, args.min_symbols,
                   args.monthly_csv, args.yearly_csv, args.trade_windows_csv)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
