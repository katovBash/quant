"""Publish machine-readable one-minute cache coverage for 15M/30M experiments."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.timeframes import MINUTE_START, SNAPSHOT_END, source_path


def main() -> None:
    cache = ROOT / "data/moex_scan"
    universe = json.loads((cache / f"universe_{SNAPSHOT_END}.json").read_text())
    symbols = [item["SECID"] for item in universe if item.get("SECTYPE") in ("1", "2")]
    present = [symbol for symbol in symbols if source_path(cache, symbol, "15M").exists()]
    report = {"source_interval": "1M", "derived_intervals": ["15M", "30M"],
              "snapshot_from": MINUTE_START, "snapshot_through": SNAPSHOT_END,
              "universe_count": len(symbols), "cached_symbols": present,
              "missing_symbols": [symbol for symbol in symbols if symbol not in set(present)],
              "cached_count": len(present),
              "note": "cache presence is not evidence that an experiment ran; inspect each results/progress.csv"}
    target = cache / "minute_coverage.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"minute cache: {len(present)}/{len(symbols)} symbols; {target}")


if __name__ == "__main__":
    main()
