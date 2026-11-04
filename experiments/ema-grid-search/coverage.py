"""Report exact completed/missing/failed coverage for the EMA grid run."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = Path(__file__).resolve().parent
OUT = EXPERIMENT / "results"
UNIVERSE = ROOT / "data/moex_scan/universe_2026-10-30.json"


def main():
    equities = [x["SECID"] for x in json.loads(UNIVERSE.read_text())
                if x.get("SECTYPE") in ("1", "2")]
    latest = {}
    path = OUT / "progress.csv"
    if path.exists():
        for row in csv.DictReader(path.open()):
            latest[row["symbol"], row["timeframe"]] = row
    report = {"equity_count": len(equities), "timeframes": {},
              "current_universe_comparison": None}
    source_info = {}

    def source_summary(symbol, tf):
        interval = 24 if tf == "1D" else 60
        key = (symbol, interval)
        if key not in source_info:
            start = "2022-01-01" if interval == 24 else "2024-01-01"
            source = ROOT / "data/moex_scan" / f"{symbol}_{interval}_{start}_2026-10-30.json"
            if source.exists():
                bars = json.loads(source.read_text())
                source_info[key] = (len(bars), bars[-1]["ts"] if bars else "")
            else:
                source_info[key] = (0, "")
        return source_info[key]
    current = OUT / "current_universe_comparison.json"
    if current.exists():
        report["current_universe_comparison"] = json.loads(current.read_text())
    for tf in ("1D", "1H", "4H"):
        complete, missing, failed, pending, stale, short = [], [], [], [], [], []
        for symbol in equities:
            target = OUT / tf / f"{symbol}.csv.gz"
            if target.exists():
                complete.append(symbol)
                _, last = source_summary(symbol, tf)
                if last[:10] < "2025-01-01":
                    stale.append({"symbol": symbol, "last_bar": last})
                n = int(latest.get((symbol, tf), {}).get("bars") or 0)
                if n and n < 203:
                    short.append({"symbol": symbol, "bars": n})
            else:
                row = latest.get((symbol, tf))
                if row is None:
                    pending.append(symbol)
                elif row["status"] == "missing_cache":
                    missing.append(symbol)
                else:
                    failed.append({"symbol": symbol, "status": row["status"],
                                   "detail": row.get("detail", "")})
        report["timeframes"][tf] = {"completed": len(complete),
                                     "missing_cache": missing, "failed": failed,
                                     "pending": pending,
                                     "stale_before_oos": stale,
                                     "history_under_203_bars": short}
    (OUT / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    for tf, value in report["timeframes"].items():
        print(tf, "complete", value["completed"], "missing", len(value["missing_cache"]),
              "failed", len(value["failed"]), "pending", len(value["pending"]),
              "stale", len(value["stale_before_oos"]))


if __name__ == "__main__":
    main()
