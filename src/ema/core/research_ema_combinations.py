"""Staged, past-only EMA12/33 pattern research on cached MOEX candles."""

from __future__ import annotations

import csv
import itertools
import json
import math
import statistics
from collections import deque
from pathlib import Path

from src.ema.core.adx_ema import SCAN, TIMEFRAMES, adx, load_bars
from src.ema.core.scan_ema import ema

ROOT = Path("experiments/.history/legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/pattern-lab")
OUT = ROOT / "execute"
CANDIDATES = ("breakout20", "engulfing", "hammer", "double_pattern", "volume", "range_expansion", "adx20")
LATE_START = "2025-01-01"


def recent(events: list[bool], length: int) -> list[bool]:
    last = -10_000
    active = []
    for i, event in enumerate(events):
        if event:
            last = i
        active.append(i - last < length)
    return active


def double_patterns(bars: list[dict]) -> tuple[list[bool], list[bool]]:
    """Two confirmed 3/3 pivots, similar extremes, neckline close breakout."""
    n = len(bars)
    bull = [False] * n
    bear = [False] * n
    lows: deque[tuple[int, float]] = deque(maxlen=2)
    highs: deque[tuple[int, float]] = deque(maxlen=2)
    low_used = high_used = -1
    for i in range(n):
        j = i - 3
        if j >= 3:
            around = bars[j - 3:j + 4]
            low = bars[j]["low"]
            high = bars[j]["high"]
            if low < min(x["low"] for x in around[:3]) and low <= min(x["low"] for x in around[4:]):
                lows.append((j, low))
            if high > max(x["high"] for x in around[:3]) and high >= max(x["high"] for x in around[4:]):
                highs.append((j, high))
        if i == 0:
            continue
        if len(lows) == 2:
            (a, p1), (b, p2) = lows
            if (p1 > 0 and low_used != b and 8 <= b - a <= 80 and i - b <= 20 and
                    abs(p2 / p1 - 1) <= 0.03):
                neckline = max(x["high"] for x in bars[a:b + 1])
                if neckline / max(p1, p2) >= 1.03 and bars[i - 1]["close"] <= neckline < bars[i]["close"]:
                    bull[i] = True
                    low_used = b
        if len(highs) == 2:
            (a, p1), (b, p2) = highs
            if (p1 > 0 and high_used != b and 8 <= b - a <= 80 and i - b <= 20 and
                    abs(p2 / p1 - 1) <= 0.03):
                neckline = min(x["low"] for x in bars[a:b + 1])
                if neckline > 0 and min(p1, p2) / neckline >= 1.03 and bars[i - 1]["close"] >= neckline > bars[i]["close"]:
                    bear[i] = True
                    high_used = b
    return recent(bull, 11), recent(bear, 11)


def gates(bars: list[dict]) -> dict[str, tuple[list[bool], list[bool]]]:
    n = len(bars)
    result = {}
    breakout_up, breakout_down = [False] * n, [False] * n
    engulf_up, engulf_down = [False] * n, [False] * n
    hammer_up, hammer_down = [False] * n, [False] * n
    volume_event = [False] * n
    range_event = [False] * n
    tr = [max(b["high"] - b["low"], abs(b["high"] - bars[i - 1]["close"]),
              abs(b["low"] - bars[i - 1]["close"])) if i else b["high"] - b["low"]
          for i, b in enumerate(bars)]
    for i, bar in enumerate(bars):
        if i >= 20:
            prior = bars[i - 20:i]
            breakout_up[i] = bar["close"] > max(x["high"] for x in prior)
            breakout_down[i] = bar["close"] < min(x["low"] for x in prior)
            volume_event[i] = bar["volume"] > 1.5 * sum(x["volume"] for x in prior) / 20
            range_event[i] = tr[i] > 1.5 * sum(tr[i - 20:i]) / 20
        if i:
            prev = bars[i - 1]
            engulf_up[i] = (prev["close"] < prev["open"] and bar["close"] > bar["open"] and
                            bar["open"] <= prev["close"] and bar["close"] >= prev["open"])
            engulf_down[i] = (prev["close"] > prev["open"] and bar["close"] < bar["open"] and
                              bar["open"] >= prev["close"] and bar["close"] <= prev["open"])
        body = max(abs(bar["close"] - bar["open"]), bar["close"] * 0.001)
        lower_wick = min(bar["open"], bar["close"]) - bar["low"]
        upper_wick = bar["high"] - max(bar["open"], bar["close"])
        hammer_up[i] = bar["close"] > bar["open"] and lower_wick >= 2 * body and upper_wick <= body
        hammer_down[i] = bar["close"] < bar["open"] and upper_wick >= 2 * body and lower_wick <= body
    result["breakout20"] = (recent(breakout_up, 6), recent(breakout_down, 6))
    result["engulfing"] = (recent(engulf_up, 4), recent(engulf_down, 4))
    result["hammer"] = (recent(hammer_up, 4), recent(hammer_down, 4))
    result["double_pattern"] = double_patterns(bars)
    result["volume"] = (recent(volume_event, 4), recent(volume_event, 4))
    result["range_expansion"] = (recent(range_event, 4), recent(range_event, 4))
    adx_values = adx(bars)
    strong = [math.isfinite(value) and value >= 20 for value in adx_values]
    result["adx20"] = (strong, strong)
    return result


def crosses(bars: list[dict]) -> list[int]:
    fast = ema([bar["close"] for bar in bars], 12)
    slow = ema([bar["close"] for bar in bars], 33)
    return [1 if i >= 1 and fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
            else -1 if i >= 1 and fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]
            else 0 for i in range(len(bars))]


def simulate(bars: list[dict], signals: list[int], gate_up: list[bool], gate_down: list[bool],
             tick: float, start: str, end: str | None = None,
             fee_bps: float = 5, dividends_per_share: dict[str, float] | None = None,
             equity_curve: list[dict] | None = None,
             trade_log: list[dict] | None = None,
             exit_signals: list[int] | None = None) -> dict:
    """Baseline next-open fills; optional ex-date dividend credit or short debit."""
    if not bars:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0,
                "pnl_rub": 0.0,
                "closed_trades": 0, "winning_trades": 0,
                "long_trades": 0, "short_trades": 0, "profit_factor": 0.0}
    cash = 1_000_000.0
    fee = fee_bps / 10_000
    position = 0
    entry_flow = 0.0
    entry_date = None
    closed_pnls = []
    long_count = short_count = 0
    peak = cash
    drawdown = 0.0
    last_close = None
    credited_dates: set[str] = set()
    for i in range(33, len(bars)):
        date = bars[i]["ts"][:10]
        if date < start:
            continue
        if end and date >= end:
            break
        current, previous = bars[i], bars[i - 1]
        last_close = current["close"]
        if dividends_per_share and date in dividends_per_share and date not in credited_dates:
            dividend = dividends_per_share[date]
            cash += position * dividend
            entry_flow -= abs(position) * dividend
            credited_dates.add(date)
        direction = signals[i - 1]
        exit_direction = exit_signals[i - 1] if exit_signals is not None else direction
        should_close = position and (
            (exit_direction and (position > 0) != (exit_direction > 0))
            or (direction and (position > 0) != (direction > 0)))
        if direction or should_close:
            equity_signal = cash + position * previous["close"]
            qty = math.floor(equity_signal * 0.25 / previous["close"])
            permitted = (gate_up[i - 1] if direction > 0 else gate_down[i - 1]) if direction else False
            if should_close:
                if position > 0:
                    proceeds = position * max(current["open"] - tick, 0) * (1 - fee)
                    cash += proceeds
                    pnl = proceeds - entry_flow
                    closed_pnls.append(pnl)
                    if trade_log is not None:
                        trade_log.append({"entry_date": entry_date, "exit_date": date,
                                          "side": "long", "pnl_rub": round(pnl, 2)})
                    long_count += 1
                else:
                    cover = -position * (current["open"] + tick) * (1 + fee)
                    cash -= cover
                    pnl = entry_flow - cover
                    closed_pnls.append(pnl)
                    if trade_log is not None:
                        trade_log.append({"entry_date": entry_date, "exit_date": date,
                                          "side": "short", "pnl_rub": round(pnl, 2)})
                    short_count += 1
                position = 0
                entry_date = None
            if direction and position == 0 and qty > 0 and permitted:
                if direction > 0:
                    cost = qty * (current["open"] + tick) * (1 + fee)
                    if cost <= cash:
                        cash -= cost
                        position = qty
                        entry_flow = cost
                        entry_date = date
                else:
                    proceeds = qty * max(current["open"] - tick, 0) * (1 - fee)
                    cash += proceeds
                    position = -qty
                    entry_flow = proceeds
                    entry_date = date
        equity = cash + position * current["close"]
        if equity_curve is not None:
            equity_curve.append({"date": date, "equity": equity, "position": position})
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    final_equity = cash + position * (last_close if last_close is not None else bars[-1]["close"])
    profits = sum(x for x in closed_pnls if x > 0)
    losses = -sum(x for x in closed_pnls if x < 0)
    return {"return_pct": round(100 * (final_equity / 1_000_000 - 1), 2),
            "pnl_rub": round(final_equity - 1_000_000, 2),
            "max_drawdown_pct": round(100 * drawdown, 2),
            "closed_trades": len(closed_pnls),
            "winning_trades": sum(x > 0 for x in closed_pnls),
            "long_trades": long_count, "short_trades": short_count,
            "profit_factor": round(profits / losses, 3) if losses else ("inf" if profits else 0.0)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    universe = json.loads((SCAN / "daily_weekly_monthly/universe.json").read_text())
    liquid = {x["SECID"] for x in json.loads((SCAN / "intraday/universe.json").read_text())}
    variants = [tuple()] + [combo for extras in range(1, 5)
                            for combo in itertools.combinations(CANDIDATES, extras)]
    rows = []
    errors = []
    for entry in universe:
        symbol = entry["SECID"]
        tick = float(entry.get("MINSTEP") or 0)
        try:
            daily = load_bars(symbol, "1D")
            train_daily = [bar for bar in daily if bar["ts"][:10] < LATE_START]
            turnover = statistics.median(bar["close"] * bar["volume"] for bar in train_daily) if train_daily else 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"symbol": symbol, "timeframe": "1D", "error": str(exc)})
            continue
        for timeframe in TIMEFRAMES:
            if timeframe in ("1H", "4H") and symbol not in liquid:
                continue
            try:
                bars = daily if timeframe == "1D" else load_bars(symbol, timeframe)
                signals = crosses(bars)
                checks = gates(bars)
                all_true = [True] * len(bars)
                start = "2024-01-01" if timeframe in ("1H", "4H") else "2022-01-01"
                for combo in variants:
                    up = [all(checks[name][0][i] for name in combo) for i in range(len(bars))] if combo else all_true
                    down = [all(checks[name][1][i] for name in combo) for i in range(len(bars))] if combo else all_true
                    train = simulate(bars, signals, up, down, tick, start, LATE_START)
                    late = simulate(bars, signals, up, down, tick, LATE_START)
                    full = simulate(bars, signals, up, down, tick, start)
                    row = {"symbol": symbol, "timeframe": timeframe,
                           "variant": "+".join(combo) if combo else "baseline",
                           "approaches": 1 + len(combo), "bars": len(bars),
                           "train_daily_turnover_rub": round(turnover, 2),
                           "first_bar": bars[0]["ts"] if bars else "",
                           "last_bar": bars[-1]["ts"] if bars else ""}
                    for prefix, result in (("train_", train), ("late_", late), ("full_", full)):
                        row.update({prefix + key: value for key, value in result.items()})
                    rows.append(row)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": str(exc)})
        if len(rows) and len({r["symbol"] for r in rows}) % 50 == 0:
            print(f"scanned {symbol}: {len(rows)} rows", flush=True)
    with (OUT / "all_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2))
    print(f"rows={len(rows)}, groups={sum(r['variant']=='baseline' for r in rows)}, errors={len(errors)}")


if __name__ == "__main__":
    main()
