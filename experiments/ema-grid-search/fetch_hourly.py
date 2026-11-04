"""Fetch missing hourly MOEX TQBR equity candles for the fixed scan snapshot.

Run only when network access is available. Each completed ticker is cached by
src.scan_ema.candles, so an interrupted download can be restarted safely.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.ema.core.scan_ema import candles  # noqa: E402

UNIVERSE = ROOT / "data/moex_scan/universe_2026-10-30.json"
CACHE = ROOT / "data/moex_scan"
OUT = Path(__file__).resolve().parent / "results"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--limit", type=int, default=0, help="optional trial limit")
    args = p.parse_args()
    universe = json.loads(UNIVERSE.read_text())
    equity = [x["SECID"] for x in universe if x.get("SECTYPE") in ("1", "2")]
    missing = [s for s in equity if not (CACHE / f"{s}_60_2024-01-01_2026-10-30.json").exists()]
    if args.limit:
        missing = missing[:args.limit]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "fetch_hourly_progress.csv"
    if not path.exists():
        path.write_text("symbol,status,bars,seconds,error\n")

    def fetch(symbol):
        started = time.monotonic()
        try:
            bars = candles(symbol, 60, "2024-01-01", "2026-10-30", CACHE)
            return symbol, "complete" if bars else "empty", len(bars), round(time.monotonic()-started, 2), ""
        except Exception as exc:
            return symbol, "error", 0, round(time.monotonic()-started, 2), str(exc).replace(",", ";")[:300]

    print(f"Fetching {len(missing)} missing hourly equity series, workers={args.workers}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for count, future in enumerate(as_completed(pool.submit(fetch, s) for s in missing), 1):
            row = future.result()
            with path.open("a", newline="") as file:
                csv.writer(file).writerow(row)
            print(f"[{count}/{len(missing)}] {row[0]} {row[1]} bars={row[2]} {row[3]}s", flush=True)


if __name__ == "__main__":
    main()
