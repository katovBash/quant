"""Poll MOEX candles and keep separate virtual strategy accounts. Never sends orders."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from papertrading.status import publish as publish_paper_status
from papertrading.setup import load_setup
from service.data_sources.moex import (MOSCOW, MarketDataUnavailable, fetch_candles,
                                       normalize_bars, parse_moscow)
from src.ema.core.scan_ema import four_hour

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies/line-retest-4h-wing1-zone05-slope/strategy.py"
LIVE_CANDLE_CACHE = Path(__file__).resolve().parents[1] / "data/moex_live"
_spec = importlib.util.spec_from_file_location("active_paper_strategy", STRATEGY_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load strategy: {STRATEGY_PATH}")
_strategy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_strategy)
STRATEGY_ID = _strategy.STRATEGY_ID
STRATEGIES_ROOT = STRATEGY_PATH.parents[1]
DEFAULT_POSITION_WEIGHT = 0.10
TRADE_COLUMNS = ("observed_at", "signal_bar", "fill_bar", "symbol", "action", "qty",
                 "price", "fee_rub", "borrow_rub", "cash_after", "position_after", "reason")
EQUITY_COLUMNS = ("observed_at", "bar_end", "symbol", "strategy_equity", "baseline_equity",
                  "cash", "position", "mark_price")
EVALUATION_EQUITY_COLUMNS = ("date", "strategy_equity", "baseline_equity")
CLOSED_COLUMNS = ("exit_date",)


def load_strategy(strategy_id: str):
    """Only strategies shipped in this repository may control a paper account."""
    if strategy_id == STRATEGY_ID:
        return _strategy
    for path in sorted(STRATEGIES_ROOT.glob("*/strategy.py")):
        if path == STRATEGY_PATH:
            continue
        spec = importlib.util.spec_from_file_location("paper_" + path.parent.name.replace("-", "_"), path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if getattr(module, "STRATEGY_ID", None) == strategy_id:
            return module
    raise ValueError(f"unregistered paper strategy: {strategy_id}")


def completed_four_hour(bars: list[dict], now: datetime) -> list[dict]:
    """Use the research's day-based four-hour grouping, withholding the live partial group."""
    if not bars:
        return []
    result = four_hour(bars)
    # A partial last group is complete only after a later trading day is observed.
    day = bars[-1]["ts"][:10]
    today = [bar for bar in bars if bar["ts"][:10] == day]
    if len(today) % 4 and now.date().isoformat() == day:
        result.pop()
    index_by_ts = {bar["ts"]: index for index, bar in enumerate(bars)}
    for index, bar in enumerate(result):
        first = index_by_ts[bar["ts"]]
        last = index_by_ts[result[index + 1]["ts"]] - 1 if index + 1 < len(result) else len(bars) - 1
        last = min(last, first + 3)
        while bars[last]["ts"][:10] != bar["ts"][:10]:
            last -= 1
        bar["end"] = bars[last]["end"]
    return result


def side_from_strategy(module, bars: list[dict], mode: str, position: int,
                       hourly_bars: list[dict] | None = None) -> str | None:
    if not hasattr(module, "signal"):
        return module.target_side([bar["close"] for bar in bars], mode, position)
    if getattr(module, "REQUIRES_HOURLY", False):
        if hourly_bars is None:
            raise ValueError("4H line strategy requires completed 1H source candles")
        event = module.signal(bars, hourly_bars=hourly_bars, position=position)
    else:
        event = module.signal(bars)
    if event == "flat":
        return "flat"
    if event in ("long", "short"):
        return event if mode == "long_short" or event == mode else "flat" if position else None
    if event is None:
        return None
    if event > 0:
        return "long" if mode in ("long", "long_short") else "flat" if position < 0 else None
    if event < 0:
        return "short" if mode in ("short", "long_short") else "flat" if position > 0 else None
    return None


def load_replay(path: Path, now: datetime, *, interval: int = 60) -> list[dict]:
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
    else:
        with path.open(newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
    return normalize_bars(rows, now, interval=interval)


def initial_state(symbol: str, bars: list[dict], observed_at: str, capital: float,
                  mode: str, fee_bps: float, slip_bps: float, borrow_bps: float,
                  lot_size: int, history_from: str,
                  position_weight: float = DEFAULT_POSITION_WEIGHT,
                  strategy_id: str = STRATEGY_ID, timeframe: str = "1H",
                  min_bars: int = 35) -> dict:
    if len(bars) < min_bars:
        raise ValueError(f"at least {min_bars} completed candles needed to seed strategy")
    return {"schema": 3, "symbol": symbol, "strategy": strategy_id,
            "timeframe": timeframe,
            "initial_capital": capital, "position_weight": position_weight,
            "mode": mode, "fee_bps": fee_bps,
            "slip_bps": slip_bps, "borrow_bps_annual": borrow_bps, "lot_size": lot_size,
            "history_from": history_from, "started_at": observed_at,
            "last_bar": bars[-1]["ts"], "last_end": bars[-1]["end"],
            "cash": capital, "position": 0, "entry_flow": 0.0, "pending": None,
            "baseline_qty": 0, "baseline_cash": capital,
            "closed_trades": 0, "gap_count": 0, "trades_log": [], "equity_log": []}


def advance(state: dict | None, bars: list[dict], observed_at: str, *, symbol: str,
            capital: float, mode: str, fee_bps: float, slip_bps: float,
            borrow_bps: float, lot_size: int, history_from: str,
            position_weight: float = DEFAULT_POSITION_WEIGHT,
            strategy_id: str = STRATEGY_ID, timeframe: str = "1H",
            strategy_module=None, min_bars: int = 35,
            hourly_bars: list[dict] | None = None) -> tuple[dict, list[dict], dict | None]:
    if mode not in ("long", "short", "long_short") or lot_size < 1 or capital <= 0 or not 0 < position_weight <= 1:
        raise ValueError("invalid paper portfolio settings")
    if any(not math.isfinite(x) or x < 0 for x in (fee_bps, slip_bps, borrow_bps)):
        raise ValueError("invalid cost settings")
    if len(bars) < min_bars:
        raise ValueError("insufficient completed candles")
    if state is None:
        return initial_state(symbol, bars, observed_at, capital, mode, fee_bps,
                             slip_bps, borrow_bps, lot_size, history_from, position_weight,
                             strategy_id, timeframe, min_bars), [], None
    if state.get("schema") != 3:
        raise ValueError("unsupported paper state schema; preserve old file and start a new output directory")
    if state.get("timeframe", "1H") != timeframe:
        raise ValueError("configuration changed after start: timeframe")
    for key, value in (("symbol", symbol), ("strategy", strategy_id),
                       ("initial_capital", capital), ("position_weight", position_weight),
                       ("mode", mode), ("fee_bps", fee_bps),
                       ("slip_bps", slip_bps), ("borrow_bps_annual", borrow_bps),
                       ("lot_size", lot_size), ("history_from", history_from)):
        if state[key] != value:
            raise ValueError(f"configuration changed after start: {key}")
    if bars[-1]["ts"] == state["last_bar"]:
        return state, [], None
    index = next((i for i, b in enumerate(bars) if b["ts"] == state["last_bar"]), None)
    if index is None or index >= len(bars) - 1:
        raise ValueError("last processed candle missing from source; no order placed")
    fresh = bars[index + 1:]
    last = fresh[-1]
    events = []
    state = dict(state)
    state["trades_log"] = list(state["trades_log"])
    state["equity_log"] = list(state["equity_log"])
    elapsed = (parse_moscow(last["end"]) - parse_moscow(state["last_end"])).total_seconds()
    if elapsed < 0:
        raise ValueError("candle end moved backwards")
    borrow = abs(state["position"]) * last["close"] * borrow_bps / 10000 * elapsed / (365 * 86400) if state["position"] < 0 else 0.0
    state["cash"] -= borrow
    if len(fresh) > 1:
        state["pending"] = None
        state["gap_count"] += 1
        events.append({"action": "GAP", "reason": f"missed {len(fresh) - 1} completed candles"})
    else:
        pending = state["pending"]
        if pending is not None:
            desired_side = 1 if pending["side"] == "long" else -1 if pending["side"] == "short" else 0
            pos = state["position"]
            mark = last["close"]
            fee = fee_bps / 10000
            slip = slip_bps / 10000
            if pos and (desired_side == 0 or (pos > 0) != (desired_side > 0)):
                price = mark * (1 - slip if pos > 0 else 1 + slip)
                qty = abs(pos)
                cost = qty * price * fee
                state["cash"] += pos * price - cost
                state["position"] = 0
                state["closed_trades"] += 1
                events.append(dict(action="CLOSE_LONG" if pos > 0 else "CLOSE_SHORT", qty=qty,
                                   price=price, fee_rub=cost, borrow_rub=borrow,
                                   signal_bar=pending["bar"], fill_bar=last["ts"],
                                   reason=strategy_id))
            if state["position"] == 0 and desired_side:
                equity = state["cash"]
                qty = math.floor((equity * position_weight / (mark * (1 + slip) * (1 + fee))) / lot_size) * lot_size
                if qty > 0:
                    price = mark * (1 + slip if desired_side > 0 else 1 - slip)
                    cost = qty * price * fee
                    debit = qty * price + cost
                    if desired_side < 0 or debit <= state["cash"]:
                        state["cash"] -= desired_side * qty * price + cost
                        state["position"] = desired_side * qty
                        state["entry_flow"] = debit if desired_side > 0 else qty * price - cost
                        events.append(dict(action="OPEN_LONG" if desired_side > 0 else "OPEN_SHORT",
                                           qty=qty, price=price, fee_rub=cost, borrow_rub=0.0,
                                           signal_bar=pending["bar"], fill_bar=last["ts"],
                                           reason=strategy_id))
            state["pending"] = None
    side = side_from_strategy(strategy_module or _strategy, bars, mode, state["position"],
                              hourly_bars=hourly_bars)
    if side == "flat":
        # Exit-only signal: handled by the same next-candle mechanism.
        state["pending"] = {"side": "flat", "bar": last["ts"]}
    elif side:
        state["pending"] = {"side": side, "bar": last["ts"]}
    state["last_bar"] = last["ts"]
    state["last_end"] = last["end"]
    mark = last["close"]
    if state["baseline_qty"] == 0:
        fee = fee_bps / 10000
        price = mark * (1 + slip_bps / 10000)
        qty = math.floor((capital * position_weight / (price * (1 + fee))) / lot_size) * lot_size
        state["baseline_qty"] = qty
        state["baseline_cash"] -= qty * price * (1 + fee)
    point = {"observed_at": observed_at, "bar_end": last["end"], "symbol": symbol,
             "strategy_equity": state["cash"] + state["position"] * mark,
             "baseline_equity": state["baseline_cash"] + state["baseline_qty"] * mark,
             "cash": state["cash"], "position": state["position"], "mark_price": mark}
    for event in events:
        event.update(observed_at=observed_at, symbol=symbol,
                     cash_after=state["cash"], position_after=state["position"])
    state["trades_log"].extend(events)
    state["equity_log"].append(point)
    return state, events, point


def append_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    """Rebuild derived CSV from the durable state; reruns cannot duplicate rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        file.flush()
        os.fsync(file.fileno())
    temp.replace(path)


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
        file.flush()
        os.fsync(file.fileno())
    temp.replace(path)


def write_evaluation_files(root: Path, state: dict) -> None:
    """Daily last observation and actual closes, excluding the initial date."""
    frozen_day = (datetime.fromisoformat(state["started_at"]).date() - timedelta(days=1)).isoformat()
    daily = {}
    for point in state["equity_log"]:
        day = point["observed_at"][:10]
        if day > frozen_day:
            daily[day] = {"date": day, "strategy_equity": point["strategy_equity"],
                          "baseline_equity": point["baseline_equity"]}
    closes = [{"exit_date": event["observed_at"][:10]}
              for event in state["trades_log"]
              if event["action"].startswith("CLOSE_") and event["observed_at"][:10] > frozen_day]
    append_csv(root / "equity.csv", EVALUATION_EQUITY_COLUMNS, list(daily.values()))
    append_csv(root / "closed_trades.csv", CLOSED_COLUMNS, closes)


def run_once(args: argparse.Namespace, now: datetime, source_bars: list[dict] | None = None) -> dict:
    root = args.output / (args.account_id or args.symbol)
    state_path = root / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    strategy_id = getattr(args, "strategy_id", STRATEGY_ID)
    timeframe = getattr(args, "timeframe", "1H")
    interval = 24 if timeframe == "1D" else 60
    module = load_strategy(strategy_id)
    if getattr(module, "SYMBOL", args.symbol) != args.symbol or getattr(module, "TIMEFRAME", timeframe) != timeframe:
        raise ValueError("strategy ticker or timeframe differs from frozen rule")
    raw = (source_bars if source_bars is not None else
           load_replay(args.replay, now, interval=interval) if args.replay else
           fetch_candles(args.symbol, args.history_from, now,
                         LIVE_CANDLE_CACHE / (f"{args.symbol}_{args.history_from}_24.json" if interval == 24
                                              else f"{args.symbol}_{args.history_from}.json"),
                         interval=interval,
                         require_ohlc=module is not _strategy))
    bars = completed_four_hour(raw, now) if timeframe == "4H" else raw
    updated, events, point = advance(state, bars, now.isoformat(), symbol=args.symbol,
                                     capital=args.capital, mode=args.mode, fee_bps=args.fee_bps,
                                     slip_bps=args.slip_bps, borrow_bps=args.borrow_bps_annual,
                                     lot_size=args.lot_size, history_from=args.history_from,
                                     position_weight=args.position_weight_pct / 100,
                                     strategy_id=strategy_id, timeframe=timeframe,
                                     strategy_module=module,
                                     min_bars=200,
                                     hourly_bars=raw if timeframe == "4H" else None)
    if updated is not state:
        save_state(state_path, updated)
    append_csv(root / "trades.csv", TRADE_COLUMNS, updated["trades_log"])
    append_csv(root / "equity_observations.csv", EQUITY_COLUMNS, updated["equity_log"])
    write_evaluation_files(root, updated)
    try:
        paper_statuses = publish_paper_status(args.output)
        paper_status = next(row["paper_status"] for row in paper_statuses
                            if row["account_id"] == root.name)
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        paper_status = f"STATUS_UNAVAILABLE: {exc}"
    return {"status": "OK", "symbol": args.symbol, "strategy": strategy_id,
            "timeframe": timeframe,
            "paper_status": paper_status,
            "initial_capital_rub": updated["initial_capital"],
            "position_weight_pct": 100 * updated["position_weight"],
            "lot_size_shares": updated["lot_size"],
            "fee_bps": updated["fee_bps"], "slip_bps": updated["slip_bps"],
            "borrow_bps_annual": updated["borrow_bps_annual"],
            "source": "replay" if args.replay else "MOEX ISS",
            "last_completed_bar": updated["last_bar"], "position": updated["position"],
            "pending": updated["pending"], "new_events": len(events),
            "orders_created": sum(e.get("action", "").startswith("OPEN_") for e in events),
            "closed_trades": updated["closed_trades"], "gap_count": updated["gap_count"]}


def poll_error(status: str, exc: Exception, observed_at: datetime, retry_seconds: int) -> dict:
    return {"status": status, "observed_at": observed_at.isoformat(),
            "orders_created": 0, "retry_after_seconds": retry_seconds,
            "error": str(exc)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--setup", type=Path, help="frozen account setup JSON copied from papertrading/setup.template.json")
    p.add_argument("--strategy", dest="strategy_id", default=STRATEGY_ID,
                   help="registered strategy ID; setup overrides this value")
    p.add_argument("--timeframe", choices=("1H", "4H", "1D"), default="1H")
    p.add_argument("--symbol", help="MOEX TQBR ticker")
    p.add_argument("--account-id", help="unique account directory name")
    p.add_argument("--output", type=Path, default=Path("papertrading/live"))
    p.add_argument("--history-from", default="2024-01-01")
    p.add_argument("--mode", choices=("long", "short", "long_short"), default="long_short")
    p.add_argument("--capital", type=float, default=1_000_000)
    p.add_argument("--position-weight-pct", type=float, default=10)
    p.add_argument("--fee-bps", type=float, default=5)
    p.add_argument("--slip-bps", type=float, default=10)
    p.add_argument("--borrow-bps-annual", type=float, default=0)
    p.add_argument("--lot-size", type=int, help="exchange lot size, verify for this ticker")
    p.add_argument("--poll-seconds", type=int, default=900)
    p.add_argument("--once", action="store_true")
    p.add_argument("--replay", type=Path, help="offline JSON/CSV candles, for testing only")
    args = p.parse_args()
    if args.setup:
        try:
            setup = load_setup(args.setup)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            p.error(str(exc))
        args.strategy_id = setup["strategy"]
        args.timeframe = setup["timeframe"]
        args.account_id = setup["account_id"]
        args.symbol = setup["symbol"]
        args.capital = setup["initial_capital_rub"]
        args.position_weight_pct = setup["position_weight_pct"]
        args.mode = setup["mode"]
        args.lot_size = setup["lot_size_shares"]
        args.fee_bps = setup["fee_bps"]
        args.slip_bps = setup["slip_bps"]
        args.borrow_bps_annual = setup["borrow_bps_annual"]
    if args.symbol is None or args.lot_size is None:
        p.error("provide --setup or both --symbol and --lot-size")
    args.symbol = args.symbol.upper()
    if (not args.symbol.isalnum() or args.poll_seconds < 1 or
            not 0 < args.position_weight_pct <= 100 or
            (args.account_id is not None and not args.account_id.replace("-", "").replace("_", "").isalnum())):
        p.error("invalid ticker or poll interval")
    while True:
        observed_at = datetime.now(MOSCOW)
        try:
            print(json.dumps(run_once(args, observed_at), ensure_ascii=False), flush=True)
        except MarketDataUnavailable as exc:
            print(json.dumps(poll_error("DATA_UNAVAILABLE", exc, observed_at, args.poll_seconds),
                             ensure_ascii=False), flush=True)
            if args.once:
                raise SystemExit(1) from exc
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(json.dumps(poll_error("PROCESSING_ERROR", exc, observed_at, args.poll_seconds),
                             ensure_ascii=False), flush=True)
            if args.once:
                raise SystemExit(1) from exc
        if args.once:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
