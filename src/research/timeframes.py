"""Load fixed research candles; derive 15M/30M only from one-minute OHLCV."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.ema.core.scan_ema import four_hour

SNAPSHOT_END = "2026-10-30"
MINUTE_START = "2026-01-01"
TIMEFRAMES = ("15M", "30M", "1H", "4H", "1D")


def source_path(cache: Path, symbol: str, timeframe: str) -> Path:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unknown timeframe: {timeframe}")
    interval = 24 if timeframe == "1D" else 1 if timeframe in ("15M", "30M") else 60
    start = "2022-01-01" if timeframe == "1D" else MINUTE_START if interval == 1 else "2024-01-01"
    return cache / f"{symbol}_{interval}_{start}_{SNAPSHOT_END}.json"


def aggregate_minutes(bars: list[dict], minutes: int) -> list[dict]:
    if minutes not in (15, 30):
        raise ValueError("only 15M and 30M are supported")
    result: list[dict] = []
    previous = None
    previous_key = None
    for bar in bars:
        stamp = datetime.fromisoformat(bar["ts"])
        if previous is not None and stamp <= previous:
            raise ValueError("minute candles must be strictly increasing")
        previous = stamp
        # Buckets follow Moscow exchange wall-clock time, not every Nth traded minute.
        key = (stamp.date(), stamp.hour, stamp.minute // minutes)
        if key != previous_key:
            result.append(dict(bar))
            previous_key = key
        else:
            current = result[-1]
            current["high"] = max(current["high"], bar["high"])
            current["low"] = min(current["low"], bar["low"])
            current["close"] = bar["close"]
            current["volume"] += bar.get("volume", 0)
    return result


def load_research_bars(cache: Path, symbol: str, timeframe: str) -> list[dict]:
    path = source_path(cache, symbol, timeframe)
    bars = json.loads(path.read_text(encoding="utf-8"))
    if timeframe in ("15M", "30M"):
        return aggregate_minutes(bars, 15 if timeframe == "15M" else 30)
    return four_hour(bars) if timeframe == "4H" else bars


def sample_period(timeframe: str) -> tuple[str, str]:
    if timeframe in ("15M", "30M"):
        return MINUTE_START, "2026-07-01"
    return ("2022-01-01" if timeframe == "1D" else "2024-01-01", "2025-01-01")
