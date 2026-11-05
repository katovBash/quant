"""Versioned, source-attributed cash events for research sensitivity runs."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path


def load_dividend_snapshot(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    snapshot = json.loads(raw)
    date.fromisoformat(snapshot["snapshot_date"])
    if len(snapshot["covered_symbols"]) != len(set(snapshot["covered_symbols"])):
        raise ValueError("duplicate covered symbol")
    seen = set()
    for event in snapshot["events"]:
        if event["type"] != "cash_dividend":
            raise ValueError("only cash dividends are supported")
        if not event["symbol"] or event["amount_per_share_rub"] <= 0:
            raise ValueError("invalid dividend symbol or amount")
        if not event["source"].startswith("https://"):
            raise ValueError("dividend needs an HTTPS source")
        record = date.fromisoformat(event["record_date"])
        effective = date.fromisoformat(event["effective_trading_date"])
        if effective > record:
            raise ValueError("effective trading date follows record date")
        key = (event["symbol"], event["effective_trading_date"])
        if key in seen:
            raise ValueError("duplicate dividend date")
        seen.add(key)
    return snapshot, hashlib.sha256(raw).hexdigest()


def dividends_for(snapshot: dict, symbol: str, bars: list[dict]) -> dict[str, float]:
    if symbol not in snapshot["covered_symbols"]:
        raise ValueError(f"corporate-event coverage not verified: {symbol}")
    if not bars:
        return {}
    dates = {bar["ts"][:10] for bar in bars}
    first_date, last_date = min(dates), max(dates)
    payouts = {}
    for event in snapshot["events"]:
        if event["symbol"] != symbol:
            continue
        effective = event["effective_trading_date"]
        if effective < first_date or effective > last_date:
            continue
        if effective not in dates:
            raise ValueError(f"missing effective trading candle: {symbol} {effective}")
        payouts[effective] = float(event["amount_per_share_rub"])
    return payouts
