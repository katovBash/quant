"""Replay the last legacy GAP event from its prior durable state and cached candles.

Dry-run by default. Requires a stopped fleet and retains pre-repair state backups.
New gaps are handled directly by service.paper_runner.advance.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from papertrading.status import publish as publish_paper_status
from guardrails.lifecycle import publish as publish_lifecycle
from service.data_sources.moex import MOSCOW, normalize_bars
from service.paper_fleet import DEFAULT_OUTPUT, DEFAULT_SETUPS, accounts
from service.paper_runner import (EQUITY_COLUMNS, LIVE_CANDLE_CACHE, TRADE_COLUMNS,
                                  advance, append_csv, completed_four_hour, save_state,
                                  write_evaluation_files, load_strategy)


def previous_statuses(log: Path) -> dict[tuple[str, str], dict]:
    result = {}
    with log.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if not line.startswith("{"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("account_id") and row.get("status") == "OK" and row.get("last_completed_bar"):
                result[(row["account_id"], row["last_completed_bar"])] = row
    return result


def reconstruct(config, state: dict, prior: dict) -> tuple[dict, list[dict]]:
    last_event = state["trades_log"][-1]
    if last_event.get("action") != "GAP" or not state["equity_log"]:
        raise ValueError(f"{config.account_id}: last event is not a legacy GAP")
    if len(state["equity_log"]) < 2:
        raise ValueError(f"{config.account_id}: no preceding equity checkpoint")
    prior_point = state["equity_log"][-2]
    if prior["position"] != prior_point["position"]:
        raise ValueError(f"{config.account_id}: prior position mismatch")
    if prior.get("gap_count") != state["gap_count"] - 1:
        raise ValueError(f"{config.account_id}: prior gap count mismatch")
    restored = json.loads(json.dumps(state))
    restored["trades_log"].pop()
    restored["equity_log"].pop()
    restored["last_bar"] = prior["last_completed_bar"]
    restored["last_end"] = prior_point["bar_end"]
    restored["cash"] = prior_point["cash"]
    restored["position"] = prior_point["position"]
    restored["pending"] = prior.get("pending")
    restored["gap_count"] = prior["gap_count"]
    interval = 24 if config.timeframe == "1D" else 60
    cache_name = (f"{config.symbol}_{config.history_from}_24_ohlc.json" if interval == 24
                  else f"{config.symbol}_{config.history_from}_ohlc.json")
    cache = LIVE_CANDLE_CACHE / cache_name
    now = datetime.now(MOSCOW)
    raw = normalize_bars(json.loads(cache.read_text(encoding="utf-8")), now, interval=interval)
    bars = completed_four_hour(raw, now) if config.timeframe == "4H" else raw
    if bars[-1]["ts"] != state["last_bar"]:
        raise ValueError(f"{config.account_id}: cached last bar differs from state")
    if not any(bar["ts"] == restored["last_bar"] and bar["end"] == restored["last_end"]
               for bar in bars):
        raise ValueError(f"{config.account_id}: prior bar absent from cache")
    updated, events, _ = advance(
        restored, bars, last_event["observed_at"], symbol=config.symbol,
        capital=config.capital, mode=config.mode, fee_bps=config.fee_bps,
        slip_bps=config.slip_bps, borrow_bps=config.borrow_bps_annual,
        lot_size=config.lot_size, history_from=config.history_from,
        position_weight=config.position_weight_pct / 100,
        strategy_id=config.strategy_id, timeframe=config.timeframe,
        strategy_module=load_strategy(config.strategy_id), min_bars=200,
        hourly_bars=raw if config.timeframe == "4H" else None)
    if updated["last_bar"] != state["last_bar"] or updated["gap_count"] != state["gap_count"]:
        raise ValueError(f"{config.account_id}: replay did not reach the same candle")
    return updated, events


def attach_bar_dates(config, state: dict) -> int:
    """Attribute each saved equity observation to its candle, not recovery day."""
    interval = 24 if config.timeframe == "1D" else 60
    cache_name = (f"{config.symbol}_{config.history_from}_24_ohlc.json" if interval == 24
                  else f"{config.symbol}_{config.history_from}_ohlc.json")
    now = datetime.now(MOSCOW)
    raw = normalize_bars(json.loads((LIVE_CANDLE_CACHE / cache_name).read_text(encoding="utf-8")),
                         now, interval=interval)
    bars = completed_four_hour(raw, now) if config.timeframe == "4H" else raw
    by_end = {bar["end"]: bar["ts"] for bar in bars}
    count = 0
    for point in state["equity_log"]:
        if not point.get("bar_ts") and point.get("bar_end") in by_end:
            point["bar_ts"] = by_end[point["bar_end"]]
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    live = DEFAULT_OUTPUT
    fleet = json.loads((live / "fleet_status.json").read_text(encoding="utf-8"))
    configs = {config.account_id: config for config in accounts(DEFAULT_SETUPS, live)}
    previous = previous_statuses(live / "fleet.log")
    changes = []
    for row in fleet["accounts"]:
        account_id = row["account_id"]
        state_path = live / account_id / "state.json"
        if not state_path.is_file():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if (not state.get("trades_log") or state["trades_log"][-1].get("action") != "GAP"
                or state["trades_log"][-1].get("recovered_after_gap")):
            continue
        if state["trades_log"][-1].get("observed_at") != fleet["observed_at"]:
            continue
        prior_point = state["equity_log"][-2]
        candidates = [value for (key_id, _), value in previous.items()
                      if key_id == account_id and value.get("last_completed_bar") < state["last_bar"]
                      and value.get("position") == prior_point["position"]
                      and value.get("gap_count") == state["gap_count"] - 1]
        prior = max(candidates, key=lambda value: value["last_completed_bar"], default=None)
        if prior is None:
            raise ValueError(f"{account_id}: preceding fleet status not found")
        updated, events = reconstruct(configs[account_id], state, prior)
        changes.append((row, state, updated, events))
    for row, old, updated, events in changes:
        print(json.dumps({"account_id": row["account_id"], "before_position": old["position"],
                          "after_position": updated["position"],
                          "replayed": [(event["action"], event.get("fill_bar")) for event in events]},
                         ensure_ascii=False))
    missing_dates = sum(sum(not point.get("bar_ts") for point in
                            json.loads((live / row["account_id"] / "state.json").read_text())["equity_log"])
                        for row in fleet["accounts"])
    if not args.apply:
        print(f"DRY_RUN accounts={len(changes)} equity_points_without_bar_date={missing_dates}")
        return
    with (live / "fleet.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        backup = live / "recovery" / fleet["observed_at"].replace(":", "-")
        backup.mkdir(parents=True, exist_ok=False)
        (backup / "fleet_status.json").write_text(json.dumps(fleet, ensure_ascii=False, indent=2) + "\n")
        revised = {row["account_id"]: (updated, events) for row, _, updated, events in changes}
        for row in fleet["accounts"]:
            account_id = row["account_id"]
            root = live / account_id
            original = json.loads((root / "state.json").read_text(encoding="utf-8"))
            (backup / f"{account_id}.json").write_text(
                json.dumps(original, ensure_ascii=False, indent=2) + "\n")
            updated, events = revised.get(account_id, (original, []))
            attach_bar_dates(configs[account_id], updated)
            save_state(root / "state.json", updated)
            append_csv(root / "trades.csv", TRADE_COLUMNS, updated["trades_log"])
            append_csv(root / "equity_observations.csv", EQUITY_COLUMNS, updated["equity_log"])
            write_evaluation_files(root, updated)
            if account_id not in revised:
                continue
            row["position"] = updated["position"]
            row["pending"] = updated["pending"]
            row["gap_count"] = updated["gap_count"]
            row["closed_trades"] = updated["closed_trades"]
            row["new_events"] = len(events)
            row["orders_created"] = sum(event["action"].startswith("OPEN_") for event in events)
        save_state(live / "fleet_status.json", fleet)
        publish_paper_status(live)
        publish_lifecycle(live, DEFAULT_SETUPS, Path(__file__).resolve().parents[1] / "strategies")
        print(f"APPLIED accounts={len(changes)} backup={backup}")


if __name__ == "__main__":
    main()
