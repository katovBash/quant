"""MOEX ISS hourly candle adapter. This module never places orders."""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


MOSCOW = ZoneInfo("Europe/Moscow")
BASE = "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR"
HTTP_BASE = BASE.replace("https://", "http://", 1)


class MarketDataUnavailable(ConnectionError):
    """MOEX candles could not be fetched; no trading decision is possible."""


def parse_moscow(value: str) -> datetime:
    return datetime.fromisoformat(value.replace(" ", "T")).replace(tzinfo=MOSCOW)


def normalize_bars(rows: list[dict], now: datetime, *, interval: int = 60) -> list[dict]:
    if interval not in (24, 60):
        raise ValueError("unsupported candle interval")
    result = []
    seen = set()
    for row in rows:
        begin = row.get("begin", row.get("ts"))
        if not begin:
            raise ValueError("bar needs begin or ts")
        # ISS `end` can be the last trade timestamp inside the hour; it does
        # not prove that the nominal 60-minute candle is complete.
        finish = parse_moscow(begin) + (timedelta(days=1) if interval == 24 else timedelta(hours=1))
        if finish > now:
            continue
        close = float(row["close"])
        bar = {"ts": str(begin), "end": finish.isoformat(),
               "open": float(row.get("open", close)),
               "high": float(row.get("high", close)),
               "low": float(row.get("low", close)),
               "close": close, "volume": float(row.get("volume", 0) or 0)}
        if not math.isfinite(bar["close"]) or bar["close"] <= 0 or bar["ts"] in seen:
            raise ValueError("invalid or duplicate completed candle")
        if not all(math.isfinite(bar[key]) for key in ("open", "high", "low", "volume")) or not bar["low"] <= bar["open"] <= bar["high"] or not bar["low"] <= bar["close"] <= bar["high"]:
            raise ValueError("invalid candle OHLCV")
        seen.add(bar["ts"])
        result.append(bar)
    if result != sorted(result, key=lambda x: x["ts"]):
        raise ValueError("candles must be ascending")
    return result


def fetch_candles(symbol: str, history_from: str, now: datetime,
                  cache_path: Path | None = None, *, require_ohlc: bool = False,
                  interval: int = 60,
                  base_url: str = BASE,
                  request_log: Callable[[dict], None] | None = None) -> list[dict]:
    """Refresh ISS candles before returning them; stale cache never authorizes an order."""
    if interval not in (24, 60):
        raise ValueError("unsupported candle interval")
    cached = json.loads(cache_path.read_text()) if cache_path and cache_path.exists() else []
    if not isinstance(cached, list) or any("begin" not in row or "close" not in row for row in cached):
        raise ValueError("invalid MOEX candle cache")
    # Old close-only caches cannot seed OHLC-dependent strategies.
    if require_ohlc and cached and any(not {"open", "high", "low"}.issubset(row) for row in cached):
        cached = []
    fetch_from = max(history_from, cached[-1]["begin"][:10]) if cached else history_from
    rows = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({"interval": interval, "from": fetch_from,
                                         "till": now.date().isoformat(), "start": offset,
                                         "iss.meta": "off"})
        url = f"{base_url}/securities/{urllib.parse.quote(symbol)}/candles.json?{query}"
        for attempt in range(3):
            started = time.monotonic()
            try:
                with urllib.request.urlopen(url, timeout=30) as response:
                    http_status = getattr(response, "status", 200)
                    payload = json.load(response)["candles"]
                if request_log:
                    request_log({"kind": "candles", "symbol": symbol, "url": url,
                                 "attempt": attempt + 1, "status": "OK", "http_status": http_status,
                                 "duration_ms": round((time.monotonic() - started) * 1000),
                                 "rows": len(payload["data"])})
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                if request_log:
                    request_log({"kind": "candles", "symbol": symbol, "url": url,
                                 "attempt": attempt + 1, "status": "ERROR",
                                 "duration_ms": round((time.monotonic() - started) * 1000),
                                 "error": str(exc)})
                if attempt == 2:
                    raise MarketDataUnavailable(f"MOEX ISS candles unavailable after retries: {exc}") from exc
                time.sleep(0.5 * (2 ** attempt))
            except (ValueError, KeyError) as exc:
                if request_log:
                    request_log({"kind": "candles", "symbol": symbol, "url": url,
                                 "attempt": attempt + 1, "status": "ERROR",
                                 "duration_ms": round((time.monotonic() - started) * 1000),
                                 "error": str(exc)})
                raise
        part = [dict(zip(payload["columns"], row)) for row in payload["data"]]
        rows.extend(part)
        if len(part) < 500:
            break
        offset += len(part)
    fields = ("begin", "open", "high", "low", "close", "volume")
    merged = {row["begin"]: {key: row[key] for key in fields if key in row} for row in cached}
    merged.update({row["begin"]: {key: row[key] for key in fields if key in row} for row in rows})
    ordered = [merged[key] for key in sorted(merged)]
    if require_ohlc and any(not {"open", "high", "low"}.issubset(row) for row in ordered):
        raise MarketDataUnavailable("MOEX ISS returned incomplete OHLC candles")
    completed = normalize_bars(ordered, now, interval=interval)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        temp.write_text(json.dumps(ordered, ensure_ascii=False))
        temp.replace(cache_path)
    return completed
