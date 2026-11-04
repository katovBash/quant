"""Keep experiment provenance when adding a subset of symbols or timeframes."""

from __future__ import annotations

import json
from pathlib import Path

from src.research.timeframes import TIMEFRAMES


def update_manifest(path: Path, current: dict, *, protocol_keys: tuple[str, ...]) -> dict:
    """Merge coverage, but reject a new protocol in an existing result directory.

    A manifest describes the union of attempted runs. Actual coverage still comes
    from the per-series results and progress file, never from this declaration.
    """
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for key in protocol_keys:
        if key in previous and key in current and previous[key] != current[key]:
            raise ValueError(f"{path}: {key} changed; use a new results directory")
    merged = {**previous, **current}
    if "symbols" in previous or "symbols" in current:
        merged["symbols"] = sorted(set(previous.get("symbols", [])) | set(current.get("symbols", [])))
    frames = set(previous.get("timeframes", [])) | set(current.get("timeframes", []))
    merged["timeframes"] = [frame for frame in TIMEFRAMES if frame in frames]
    if "late_start_by_timeframe" in previous or "late_start_by_timeframe" in current:
        merged["late_start_by_timeframe"] = {
            **previous.get("late_start_by_timeframe", {}),
            **current.get("late_start_by_timeframe", {}),
        }
    if "minute_candles_required_for" in previous or "minute_candles_required_for" in current:
        minutes = set(previous.get("minute_candles_required_for", [])) | set(current.get("minute_candles_required_for", []))
        merged["minute_candles_required_for"] = [frame for frame in TIMEFRAMES if frame in minutes]
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return merged
