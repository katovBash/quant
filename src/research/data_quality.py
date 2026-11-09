"""Conservative per-ticker quality indicators for cached research candles."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from src.research.timeframes import source_path

HALTS = Path(__file__).resolve().parents[2] / "data/candles/market_halts.json"


def documented_missing_hours() -> tuple[str, ...]:
    """Only exchange-confirmed full-hour gaps; other gaps remain blockers."""
    try:
        payload = json.loads(HALTS.read_text(encoding="utf-8"))
        return tuple(sorted(item["start"] for item in payload["documented_missing_1h_candles"]))
    except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
        return ()


@lru_cache(maxsize=256)
def _audit_cached(path_text: str, mtime_ns: int, timeframe: str,
                  documented_hours: tuple[str, ...]) -> dict:
    bars = json.loads(Path(path_text).read_text(encoding="utf-8"))
    invalid = 0
    possible_holes = 0
    explained_holes = 0
    previous = None
    # Research 4H bars are assembled from the same hourly source file.
    expected_seconds = 3600 if timeframe in ("1H", "4H") else None
    for bar in bars:
        stamp = datetime.fromisoformat(bar["ts"])
        high, low = float(bar["high"]), float(bar["low"])
        if (previous is not None and stamp <= previous
                or low > high or not low <= float(bar["open"]) <= high
                or not low <= float(bar["close"]) <= high):
            invalid += 1
        if (expected_seconds and previous is not None and stamp.date() == previous.date()
                and (stamp - previous).total_seconds() > expected_seconds * 1.5):
            missing = []
            cursor = previous + timedelta(seconds=expected_seconds)
            while cursor < stamp:
                missing.append(cursor.isoformat(sep=" "))
                cursor += timedelta(seconds=expected_seconds)
            if missing and all(hour in documented_hours for hour in missing):
                explained_holes += len(missing)
            else:
                possible_holes += 1
        previous = stamp
    return {"status": "invalid" if invalid else "possible_gaps" if possible_holes else "basic_check_ok",
            "bars": len(bars), "invalid_bars": invalid,
            "possible_intraday_gaps": possible_holes,
            "documented_market_halt_hours": explained_holes,
            "note": "Intraday gaps are heuristic; a quiet instrument or session break can be legitimate."}


def candle_quality(cache: Path, symbol: str, timeframe: str) -> dict:
    try:
        path = source_path(cache, symbol, timeframe)
        if not path.exists():
            return {"status": "missing_snapshot", "bars": 0,
                    "invalid_bars": 0, "possible_intraday_gaps": None}
        return _audit_cached(str(path), path.stat().st_mtime_ns, timeframe,
                             documented_missing_hours())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "audit_error", "error": str(exc),
                "bars": 0, "invalid_bars": None, "possible_intraday_gaps": None}
