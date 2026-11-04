"""Exploratory neighborhood check for EMA long+short on three named equities.

This is a shared-history screen, not an independent validation or a promotion.
"""

from __future__ import annotations

import csv
import gzip
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYMBOLS = ("PLZL", "VTBR", "GAZP")
FRAMES = ("1H", "4H")
FIELDS = ("timeframe", "fast", "slow", "median_return_pct", "min_return_pct",
          "median_late_return_pct", "min_closed_trades", "neighbor_pass_rate",
          "neighbor_count")


def eligible(row: dict) -> bool:
    return (int(row["closed_trades"]) >= 100 and int(row["oos_trades"]) >= 30
            and float(row["net_return_pct"]) > 0 and float(row["oos_return_pct"]) > 0
            and float(row["profit_factor"]) > 1.2
            and abs(float(row["max_drawdown_pct"])) <= 20)


def load(timeframe: str, symbol: str) -> dict[tuple[int, int], dict]:
    source = ROOT / "results" / timeframe / f"{symbol}.csv.gz"
    with gzip.open(source, "rt", encoding="utf-8") as stream:
        return {(int(row["fast"]), int(row["slow"])): row
                for row in csv.DictReader(stream) if row["mode"] == "long_short"}


def analyze() -> list[dict]:
    output = []
    for timeframe in FRAMES:
        by_symbol = {symbol: load(timeframe, symbol) for symbol in SYMBOLS}
        pairs = set.intersection(*(set(rows) for rows in by_symbol.values()))
        passed = {pair for pair in pairs if all(eligible(by_symbol[symbol][pair])
                                               for symbol in SYMBOLS)}
        for fast, slow in sorted(passed):
            neighbors = [(f, s) for f in range(max(2, fast - 2), fast + 3)
                         for s in range(max(f + 1, slow - 5), slow + 6)
                         if (f, s) in pairs and (f, s) != (fast, slow)]
            rows = [by_symbol[symbol][fast, slow] for symbol in SYMBOLS]
            returns = [float(row["net_return_pct"]) for row in rows]
            late = [float(row["oos_return_pct"]) for row in rows]
            output.append(dict(timeframe=timeframe, fast=fast, slow=slow,
                               median_return_pct=round(statistics.median(returns), 2),
                               min_return_pct=round(min(returns), 2),
                               median_late_return_pct=round(statistics.median(late), 2),
                               min_closed_trades=min(int(row["closed_trades"]) for row in rows),
                               neighbor_pass_rate=round(sum(pair in passed for pair in neighbors)
                                                        / len(neighbors), 3) if neighbors else 0,
                               neighbor_count=len(neighbors)))
    return output


def main() -> None:
    rows = analyze()
    target = ROOT / "results/robustness_3_symbols.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} combinations pass the preliminary gate on all three symbols")
    for timeframe in FRAMES:
        subset = [r for r in rows if r["timeframe"] == timeframe
                  and r["neighbor_pass_rate"] >= 0.75]
        subset.sort(key=lambda r: (r["median_return_pct"], r["min_return_pct"]), reverse=True)
        print(timeframe, "stable candidates", len(subset), "top 5:")
        for row in subset[:5]:
            print(row)


if __name__ == "__main__":
    main()
