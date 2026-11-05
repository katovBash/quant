"""Causal hourly signals and matched controls for scheduled rate decisions."""

from __future__ import annotations

from datetime import date, timedelta


def event_signals(bars: list[dict], dates: set[str], direction: str,
                  hold_bars: int) -> tuple[list[int], list[int]]:
    if direction not in {"continuation", "reversal"} or hold_bars < 1:
        raise ValueError("invalid event variant")
    entries, exits = [0] * len(bars), [0] * len(bars)
    for i, bar in enumerate(bars):
        if bar["ts"][:10] not in dates or bar["ts"][11:19] != "14:00:00":
            continue
        if i + hold_bars + 1 >= len(bars):
            continue
        if bars[i + 1]["ts"][:10] != bar["ts"][:10] or bars[i + 1]["ts"][11:19] != "15:00:00":
            continue
        movement = (bar["close"] > bar["open"]) - (bar["close"] < bar["open"])
        if movement == 0:
            continue
        side = movement if direction == "continuation" else -movement
        entries[i] = side
        exits[i + hold_bars] = -side
    return entries, exits


def matched_event_rows(symbol: str, bars: list[dict], dates: set[str]) -> tuple[list[dict], list[dict]]:
    """Compare 14:00-15:00 returns to the same hour seven days earlier."""
    lookup = {bar["ts"]: bar for bar in bars}
    rows, missing = [], []
    for event_date in sorted(dates):
        prior_date = (date.fromisoformat(event_date) - timedelta(days=7)).isoformat()
        event = lookup.get(event_date + " 14:00:00")
        control = lookup.get(prior_date + " 14:00:00")
        next_bar = lookup.get(event_date + " 15:00:00")
        if not event or not control or not next_bar or event["open"] <= 0 or control["open"] <= 0:
            missing.append({"symbol": symbol, "event_date": event_date,
                            "reason": "missing_14_or_15_or_matched_hour"})
            continue
        event_return = 100 * (event["close"] / event["open"] - 1)
        control_return = 100 * (control["close"] / control["open"] - 1)
        rows.append({"symbol": symbol, "event_date": event_date,
                     "control_date": prior_date,
                     "event_hour_return_pct": round(event_return, 6),
                     "control_hour_return_pct": round(control_return, 6),
                     "event_abs_return_pct": round(abs(event_return), 6),
                     "control_abs_return_pct": round(abs(control_return), 6),
                     "abs_return_difference_pp": round(abs(event_return) - abs(control_return), 6),
                     "event_volume": event.get("volume", 0),
                     "control_volume": control.get("volume", 0),
                     "volume_ratio": round(event.get("volume", 0) / control["volume"], 6)
                     if control.get("volume", 0) > 0 else ""})
    return rows, missing


def decision_side(previous_rate: float, announced_rate: float, mapping: str) -> int:
    """Map an already published rate decision to a fixed position direction."""
    if mapping not in {"conventional", "inverse", "hold_long", "hold_short"}:
        raise ValueError("unknown decision mapping")
    if announced_rate == previous_rate:
        return 1 if mapping == "hold_long" else -1 if mapping == "hold_short" else 0
    conventional = -1 if announced_rate > previous_rate else 1
    return -conventional if mapping == "inverse" else conventional


def decision_signals(bars: list[dict], decisions: dict[str, dict], mapping: str,
                     hold_bars: int) -> tuple[list[int], list[int]]:
    """Wait through a complete 14:00-15:00 bar, then enter on the 15:00 open."""
    if hold_bars < 1:
        raise ValueError("hold_bars must be positive")
    entries, exits = [0] * len(bars), [0] * len(bars)
    for i, bar in enumerate(bars):
        date_key = bar["ts"][:10]
        decision = decisions.get(date_key)
        if decision is None or bar["ts"][11:19] != "14:00:00":
            continue
        if i + hold_bars + 1 >= len(bars):
            continue
        if bars[i + 1]["ts"] != date_key + " 15:00:00":
            continue
        side = decision_side(decision["previous_rate"], decision["announced_rate"], mapping)
        if side:
            entries[i] = side
            exits[i + hold_bars] = -side
    return entries, exits


def decision_outcome_rows(symbol: str, bars: list[dict], decisions: dict[str, dict],
                          mapping: str, hold_bars: int) -> list[dict]:
    """Per-event approximate 25%-position net returns for date-level diagnostics."""
    result = []
    for i, bar in enumerate(bars):
        date_key = bar["ts"][:10]
        decision = decisions.get(date_key)
        if decision is None or bar["ts"][11:19] != "14:00:00":
            continue
        if i + hold_bars + 1 >= len(bars) or bars[i + 1]["ts"] != date_key + " 15:00:00":
            continue
        side = decision_side(decision["previous_rate"], decision["announced_rate"], mapping)
        if not side:
            continue
        entry = bars[i + 1]["open"]
        exit_price = bars[i + hold_bars + 1]["open"]
        if entry <= 0 or exit_price <= 0:
            continue
        gross_position_return = 100 * side * (exit_price / entry - 1)
        result.append({"symbol": symbol, "event_date": date_key, "mapping": mapping,
                       "hold_bars": hold_bars, "rate_change_bp": round(
                           100 * (decision["announced_rate"] - decision["previous_rate"]), 2),
                       "side": "long" if side > 0 else "short",
                       "gross_position_return_pct": round(gross_position_return, 6),
                       "approx_net_position_return_pct": round(gross_position_return - 0.3, 6),
                       "approx_account_return_pct": round(0.25 * (gross_position_return - 0.3), 6)})
    return result
