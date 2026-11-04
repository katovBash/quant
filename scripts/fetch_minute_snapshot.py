"""Cache MOEX TQBR one-minute candles for 15M/30M research.

Read-only MOEX requests. Each ticker is checkpointed separately; repeat the
command after network failures. The fixed snapshot stops on 2026-10-30.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.ema.core.scan_ema import candles
from src.research.timeframes import MINUTE_START, SNAPSHOT_END, source_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", help="optional ticker subset for a smoke run")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        parser.error("workers must be between 1 and 8")
    universe = json.loads((ROOT / f"data/moex_scan/universe_{SNAPSHOT_END}.json").read_text())
    symbols = [item["SECID"] for item in universe if item.get("SECTYPE") in ("1", "2")]
    if args.symbols:
        unknown = sorted(set(args.symbols) - set(symbols))
        if unknown:
            parser.error(f"unknown TQBR tickers: {', '.join(unknown)}")
        symbols = [symbol for symbol in symbols if symbol in args.symbols]
    cache = ROOT / "data/moex_scan"
    output = ROOT / "data/moex_scan/minute_fetch_progress.csv"
    if not output.exists():
        output.write_text("symbol,status,bars,seconds,detail\n", encoding="utf-8")

    def fetch(symbol: str) -> tuple:
        started = time.monotonic()
        path = source_path(cache, symbol, "15M")
        if path.exists():
            return symbol, "cached", 0, round(time.monotonic() - started, 2), ""
        try:
            bars = candles(symbol, 1, MINUTE_START, SNAPSHOT_END, cache)
            status = "complete" if bars else "empty"
            return symbol, status, len(bars), round(time.monotonic() - started, 2), ""
        except (OSError, RuntimeError, ValueError, KeyError) as exc:
            return symbol, "error", 0, round(time.monotonic() - started, 2), str(exc)[:250]

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, symbol): symbol for symbol in symbols}
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with output.open("a", encoding="utf-8", newline="") as stream:
                csv.writer(stream).writerow(row)
            print(f"[{index}/{len(symbols)}] {row[0]}: {row[1]} bars={row[2]}", flush=True)


if __name__ == "__main__":
    main()
