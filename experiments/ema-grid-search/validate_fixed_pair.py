"""Extract one frozen EMA pair from every completed ticker result.

This is a seen-history transfer check, never an independent holdout.
"""

from __future__ import annotations

import argparse
import csv
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIELDS = ("symbol", "timeframe", "fast", "slow", "mode", "bars", "closed_trades",
          "winning_trades", "net_return_pct", "buy_hold_return_pct", "profit_factor",
          "max_drawdown_pct", "oos_trades", "oos_winning_trades", "oos_return_pct",
          "oos_buy_hold_pct", "oos_profit_factor", "oos_drawdown_pct", "status",
          "evidence_class")


def find_pair(path: Path, fast: int, slow: int, mode: str) -> dict | None:
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if (int(row["fast"]) == fast and int(row["slow"]) == slow
                    and row["mode"] == mode):
                return row
    return None


def extract(fast: int, slow: int, timeframe: str, mode: str, output: Path) -> list[dict]:
    if not 2 <= fast < slow <= 200:
        raise ValueError("require 2 <= fast < slow <= 200")
    source = ROOT / "results" / timeframe
    files = sorted(source.glob("*.csv.gz"))
    if not files:
        raise ValueError(f"no results for {timeframe}")
    rows = []
    for path in files:
        row = find_pair(path, fast, slow, mode)
        if row is None:
            row = {"symbol": path.name.removesuffix(".csv.gz"), "timeframe": timeframe,
                   "fast": fast, "slow": slow, "mode": mode, "status": "missing_pair"}
        else:
            row["status"] = "tested"
        row["evidence_class"] = "seen_history"
        rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", type=int, required=True)
    parser.add_argument("--slow", type=int, required=True)
    parser.add_argument("--timeframe", choices=("1D", "1H", "4H"), required=True)
    parser.add_argument("--mode", choices=("long", "short", "long_short"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows = extract(args.fast, args.slow, args.timeframe, args.mode, args.out)
    tested = [r for r in rows if r["status"] == "tested"]
    positive = sum(float(r["net_return_pct"]) > 0 for r in tested)
    print(f"tested={len(tested)} positive={positive} missing={len(rows)-len(tested)} out={args.out}")


if __name__ == "__main__":
    main()
