"""Generate one machine-readable status index from experiment output files."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def report() -> dict:
    coverage = json.loads((ROOT / "data/moex_scan/minute_coverage.json").read_text())
    universe = set(coverage["cached_symbols"] + coverage["missing_symbols"])
    experiments = {}
    folders = list((ROOT / "experiments").glob("*-grid-search"))
    folders += list((ROOT / "experiments/double-indicator").glob("*/"))
    for folder in sorted(folders):
        results = folder / "results"
        manifest = results / "manifest.json"
        if not manifest.exists():
            continue
        protocol = json.loads(manifest.read_text())
        progress_path = results / "progress.csv"
        latest = {}
        if progress_path.exists():
            with progress_path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    latest[(row["symbol"], row["timeframe"])] = row["status"]
        frames = {}
        for timeframe in ("15M", "30M", "1H", "4H", "1D"):
            folder_path = results / timeframe
            completed = {file.name.split(".")[0] for file in folder_path.glob("*.csv*")} if folder_path.exists() else set()
            if folder_path.exists():
                completed.update(path.parent.name for path in folder_path.glob("*/forecast.csv"))
            if not completed:
                completed = {symbol for (symbol, tf), status in latest.items()
                             if tf == timeframe and status == "complete"}
            frame = {"completed_tickers": len(completed),
                     "recorded_runs": sum(tf == timeframe for _, tf in latest),
                     "configured_in_manifest": timeframe in protocol.get("timeframes", [])}
            if timeframe in ("15M", "30M"):
                frame["minute_cache_tickers"] = coverage["cached_count"]
                frame["state"] = ("complete_or_partial" if completed else
                                  "ready_to_run" if coverage["cached_count"] else "awaiting_minute_candles")
            frames[timeframe] = frame
        key = str(folder.relative_to(ROOT / "experiments"))
        experiments[key] = {"frames": frames,
                                    "source_manifest": str(manifest.relative_to(ROOT)),
                                    "source_progress": str(progress_path.relative_to(ROOT))}
    transition = ROOT / "experiments/market-regime-grid-search/transition-results"
    if transition.exists():
        progress_path = transition / "progress.csv"
        frames = {}
        for timeframe in ("15M", "30M", "1H", "4H", "1D"):
            frame_dir = transition / timeframe
            completed = len(list(frame_dir.glob("*/summary.csv")))
            recorded = 0
            if progress_path.exists():
                with progress_path.open(encoding="utf-8", newline="") as stream:
                    recorded = sum(row["timeframe"] == timeframe for row in csv.DictReader(stream))
            frame = {"completed_tickers": completed, "recorded_runs": recorded}
            if timeframe in ("15M", "30M"):
                frame["minute_cache_tickers"] = coverage["cached_count"]
                frame["state"] = "complete_or_partial" if completed else "awaiting_minute_candles"
            frames[timeframe] = frame
        experiments["market-regime-transition"] = {
            "frames": frames,
            "source_manifest": "experiments/market-regime-grid-search/transition_protocol.json",
            "source_progress": str(progress_path.relative_to(ROOT)),
        }
    return {"universe_tickers": len(universe), "minute_cache_tickers": coverage["cached_count"],
            "experiments": experiments}


if __name__ == "__main__":
    output = ROOT / "experiments/status.json"
    output.write_text(json.dumps(report(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
