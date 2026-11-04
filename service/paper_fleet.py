"""Run configured virtual accounts with one MOEX candle refresh per ticker."""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from papertrading.setup import load_setup
from service.data_sources.moex import BASE, HTTP_BASE, MOSCOW, MarketDataUnavailable, fetch_candles
from service.paper_runner import LIVE_CANDLE_CACHE, load_strategy, run_once, save_state

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETUPS = ROOT / "papertrading/setups/fleet"
DEFAULT_OUTPUT = ROOT / "papertrading/live"
DEFAULT_UNIVERSE = ROOT / "data/moex_scan/universe_2026-10-30.json"


def discover_new_setups(setup_dir: Path, strategies_dir: Path,
                        universe_path: Path = DEFAULT_UNIVERSE) -> list[Path]:
    """Create frozen accounts for the top ranked stocks of each fixed rule."""
    existing = set()
    for path in setup_dir.glob("*.json"):
        setup = load_setup(path)
        existing.add((setup["strategy"], setup["symbol"], setup["timeframe"]))
    universe = json.loads(universe_path.read_text(encoding="utf-8"))
    lots = {row["SECID"]: row["LOTSIZE"] for row in universe
            if isinstance(row.get("LOTSIZE"), int) and row["LOTSIZE"] > 0}
    created = []
    for path in sorted(strategies_dir.glob("*/strategy.py")):
        if not (path.parent / "README.md").exists() or not (path.parent / "strategy.pine").exists():
            continue
        spec = importlib.util.spec_from_file_location("paper_auto_" + path.parent.name.replace("-", "_"), path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        strategy_id = getattr(module, "STRATEGY_ID", None)
        timeframe = getattr(module, "TIMEFRAME", None)
        selection_path = path.parent / "selection.json"
        ranked = json.loads(selection_path.read_text(encoding="utf-8")) if selection_path.exists() else None
        if ranked and (ranked.get("id") != strategy_id or ranked.get("timeframe") != timeframe):
            raise ValueError(f"selection does not match frozen rule: {selection_path}")
        symbols = ([row["symbol"] for row in ranked["top10"]]
                   if ranked and ranked["status"] == "HISTORICAL_RANKING" else
                   getattr(module, "PAPER_SYMBOLS", None))
        if symbols is None:
            symbol = getattr(module, "SYMBOL", None)
            symbols = [symbol] if symbol else []
        if not strategy_id or timeframe not in ("1H", "4H", "1D") or not symbols or not callable(getattr(module, "signal", None)) and not callable(getattr(module, "target_side", None)):
            continue
        if not isinstance(symbols, (list, tuple)) or any(not isinstance(s, str) or not s.isalnum() or not s.isupper() for s in symbols):
            continue
        for symbol in symbols:
            key = (strategy_id, symbol, timeframe)
            if key in existing:
                continue
            lot = lots.get(symbol)
            if not lot:
                print(json.dumps({"status": "SETUP_SKIPPED", "strategy": strategy_id,
                                  "symbol": symbol, "reason": "lot size absent from universe snapshot"},
                                 ensure_ascii=False), flush=True)
                continue
            slug = f"auto-{symbol.lower()}-{path.parent.name}.json"
            target = setup_dir / slug
            setup = {"account_id": f"{symbol}-{path.parent.name}".upper(),
                     "symbol": symbol, "strategy": strategy_id, "timeframe": timeframe,
                     "initial_capital_rub": 1_000_000, "position_weight_pct": 10,
                     "mode": "long_short", "lot_size_shares": lot, "fee_bps": 5,
                     "slip_bps": 10, "borrow_bps_annual": 0, "stop_loss_pct": None}
            target.write_text(json.dumps(setup, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            load_setup(target)
            existing.add(key)
            created.append(target)
    return created


def accounts(setup_dir: Path, output: Path) -> list[argparse.Namespace]:
    result = []
    seen = set()
    for path in sorted(setup_dir.glob("*.json")):
        setup = load_setup(path)
        module = load_strategy(setup["strategy"])
        if (getattr(module, "SYMBOL", setup["symbol"]) != setup["symbol"] or
                getattr(module, "TIMEFRAME", setup["timeframe"]) != setup["timeframe"]):
            raise ValueError(f"strategy scope mismatch in {path}")
        if setup["account_id"] in seen:
            raise ValueError(f"duplicate account: {setup['account_id']}")
        seen.add(setup["account_id"])
        result.append(argparse.Namespace(
            account_id=setup["account_id"], symbol=setup["symbol"],
            strategy_id=setup["strategy"], timeframe=setup["timeframe"],
            capital=setup["initial_capital_rub"],
            position_weight_pct=setup["position_weight_pct"], mode=setup["mode"],
            lot_size=setup["lot_size_shares"], fee_bps=setup["fee_bps"],
            slip_bps=setup["slip_bps"], borrow_bps_annual=setup["borrow_bps_annual"],
            history_from="2022-01-01" if setup["timeframe"] == "1D" else "2024-01-01",
            output=output, replay=None))
    if not result:
        raise ValueError(f"no paper setups in {setup_dir}")
    return result


def append_request_log(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(MOSCOW).isoformat(), "process": "quant-paper-fleet", **entry}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def poll(configs: list[argparse.Namespace], now: datetime, *, preflight: bool = True,
         request_log: Path | None = None) -> list[dict]:
    rows = []
    base_url = BASE
    def log(entry: dict) -> None:
        if request_log:
            try:
                append_request_log(request_log, entry)
            except OSError as exc:
                print(json.dumps({"status": "REQUEST_LOG_ERROR", "error": str(exc)},
                                 ensure_ascii=False), flush=True)

    if preflight:
        url = BASE + ".json?iss.meta=off"
        started = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=6) as response:
                if response.status != 200:
                    raise MarketDataUnavailable(f"HTTPS preflight HTTP {response.status}")
                http_status = response.status
            log({"kind": "preflight", "url": url, "status": "OK",
                 "http_status": http_status, "duration_ms": round((time.monotonic() - started) * 1000)})
        except (urllib.error.URLError, TimeoutError, MarketDataUnavailable) as secure_exc:
            log({"kind": "preflight", "url": url, "status": "ERROR",
                 "duration_ms": round((time.monotonic() - started) * 1000),
                 "error": str(secure_exc)})
            url = HTTP_BASE + ".json?iss.meta=off"
            started = time.monotonic()
            try:
                with urllib.request.urlopen(url, timeout=6) as response:
                    if response.status != 200:
                        raise MarketDataUnavailable(f"HTTP fallback preflight HTTP {response.status}")
                    http_status = response.status
                log({"kind": "preflight", "url": url, "status": "OK",
                     "http_status": http_status, "duration_ms": round((time.monotonic() - started) * 1000)})
                base_url = HTTP_BASE
                print(json.dumps({"status": "HTTP_FALLBACK", "reason": str(secure_exc),
                                  "source": "MOEX ISS HTTP (unencrypted)"}, ensure_ascii=False), flush=True)
            except (urllib.error.URLError, TimeoutError, MarketDataUnavailable) as fallback_exc:
                log({"kind": "preflight", "url": url, "status": "ERROR",
                     "duration_ms": round((time.monotonic() - started) * 1000),
                     "error": str(fallback_exc)})
                return [{"account_id": config.account_id, "status": "DATA_UNAVAILABLE",
                         "observed_at": now.isoformat(), "orders_created": 0,
                         "error": f"MOEX ISS HTTPS: {secure_exc}; HTTP: {fallback_exc}"} for config in configs]
    grouped = {}
    for config in configs:
        interval = 24 if config.timeframe == "1D" else 60
        grouped.setdefault((config.symbol, interval), []).append(config)
    for (symbol, interval), selected in grouped.items():
        try:
            kwargs = {"require_ohlc": True, "interval": interval}
            if base_url == HTTP_BASE:
                kwargs["base_url"] = HTTP_BASE
            if request_log:
                kwargs["request_log"] = log
            cache_name = (f"{symbol}_{selected[0].history_from}_24_ohlc.json" if interval == 24
                          else f"{symbol}_{selected[0].history_from}_ohlc.json")
            raw = fetch_candles(symbol, selected[0].history_from, now,
                                LIVE_CANDLE_CACHE / cache_name,
                                **kwargs)
        except (MarketDataUnavailable, OSError, ValueError, KeyError) as exc:
            for config in selected:
                rows.append({"account_id": config.account_id, "status": "DATA_UNAVAILABLE",
                             "observed_at": now.isoformat(), "orders_created": 0, "error": str(exc)})
            continue
        for config in selected:
            try:
                result = run_once(config, now, source_bars=raw)
                if base_url == HTTP_BASE:
                    result["source"] = "MOEX ISS HTTP (unencrypted)"
                result["account_id"] = config.account_id
                rows.append(result)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                rows.append({"account_id": config.account_id, "status": "PROCESSING_ERROR",
                             "observed_at": now.isoformat(), "orders_created": 0, "error": str(exc)})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setups", type=Path, default=DEFAULT_SETUPS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--poll-seconds", type=int, default=900)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_seconds < 1:
        parser.error("poll seconds must be positive")
    strategies_dir = ROOT / "strategies"
    for path in discover_new_setups(args.setups, strategies_dir):
        print(json.dumps({"status": "SETUP_ADDED", "path": str(path)}, ensure_ascii=False), flush=True)
    configs = accounts(args.setups, args.output)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "fleet.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("another paper fleet process is already running")
        (args.output / "fleet.pid").write_text(str(os.getpid()) + "\n")
        try:
            while True:
                try:
                    for path in discover_new_setups(args.setups, strategies_dir):
                        print(json.dumps({"status": "SETUP_ADDED", "path": str(path)}, ensure_ascii=False), flush=True)
                    configs = accounts(args.setups, args.output)
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    print(json.dumps({"status": "SETUP_ERROR", "error": str(exc)}, ensure_ascii=False), flush=True)
                now = datetime.now(MOSCOW)
                rows = poll(configs, now, request_log=args.output / "fleet_requests.ndjson")
                save_state(args.output / "fleet_status.json", {"observed_at": now.isoformat(), "accounts": rows})
                for row in rows:
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                if args.once:
                    raise SystemExit(1 if any(row["status"] != "OK" for row in rows) else 0)
                time.sleep(args.poll_seconds)
        finally:
            (args.output / "fleet.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
