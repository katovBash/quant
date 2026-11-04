"""Start-date sensitivity for the fixed EMA25/0.5 ATR daily SMLT candidate."""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.standalone_grid import CACHE, UNIVERSE, ema_level_signals, load_bars

OUT = Path(__file__).resolve().parent / "results" / "ema25-atr05-1d-smlt-robustness.json"


def add_months(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def longest_underwater(curve: list[dict]) -> dict:
    """Longest calendar stretch below the previous equity high, including an open stretch."""
    peak = 1_000_000.0
    start = None
    longest = {"calendar_days": 0, "start": None, "end": None, "recovered": True}
    for point in curve:
        day = date.fromisoformat(point["date"])
        if point["equity"] >= peak:
            peak = point["equity"]
            if start is not None:
                candidate = {"calendar_days": (day - start).days,
                             "start": start.isoformat(), "end": day.isoformat(), "recovered": True}
                if candidate["calendar_days"] > longest["calendar_days"]:
                    longest = candidate
                start = None
        elif start is None:
            start = day
    if start is not None:
        day = date.fromisoformat(curve[-1]["date"])
        candidate = {"calendar_days": (day - start).days,
                     "start": start.isoformat(), "end": day.isoformat(), "recovered": False}
        if candidate["calendar_days"] > longest["calendar_days"]:
            longest = candidate
    return longest


def hold_return(bars: list[dict], tick: float, start: date, end: date) -> float:
    selected = [bar for bar in bars if start.isoformat() <= bar["ts"][:10] < end.isoformat()]
    if not selected:
        return 0.0
    quantity = math.floor(250_000 / selected[0]["open"])
    cost = quantity * (selected[0]["open"] + tick) * 1.0005
    proceeds = quantity * max(selected[-1]["close"] - tick, 0) * 0.9995
    return round(100 * (proceeds - cost) / 1_000_000, 2)


def analyze(bars: list[dict], tick: float) -> dict:
    signals = ema_level_signals(bars, 25, 0.5)
    allowed = [True] * len(bars)
    curve: list[dict] = []
    full = simulate(bars, signals, allowed, allowed, tick, "2022-01-01", equity_curve=curve)
    final_day = date.fromisoformat(bars[-1]["ts"][:10])
    windows = {}
    for months in (1, 6, 12, 24):
        rows = []
        start = date(2022, 1, 1)
        while add_months(start, months) <= final_day:
            end = add_months(start, months)
            result = simulate(bars, signals, allowed, allowed, tick,
                              start.isoformat(), end.isoformat())
            rows.append({"start": start.isoformat(), "end_exclusive": end.isoformat(),
                         "return_pct": result["return_pct"],
                         "buy_hold_return_pct": hold_return(bars, tick, start, end),
                         "closed_trades": result["closed_trades"],
                         "max_drawdown_pct": result["max_drawdown_pct"]})
            start = add_months(start, 1)
        windows[str(months)] = {
            "count": len(rows),
            "negative_count": sum(row["return_pct"] < 0 for row in rows),
            "worst": min(rows, key=lambda row: row["return_pct"]) if rows else None,
            "best": max(rows, key=lambda row: row["return_pct"]) if rows else None,
            "all": rows,
        }
    years = []
    for year in range(2022, final_day.year + 1):
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        result = simulate(bars, signals, allowed, allowed, tick,
                          start.isoformat(), end.isoformat())
        years.append({"year": year, "partial": end > final_day,
                      "return_pct": result["return_pct"],
                      "buy_hold_return_pct": hold_return(bars, tick, start, end),
                      "closed_trades": result["closed_trades"]})
    return {"symbol": "SMLT", "timeframe": "1D", "variant": "ema_level_25_0.5",
            "mode": "long_short", "data_first": bars[0]["ts"], "data_last": bars[-1]["ts"],
            "model": "same next-open simulator as the grid; 25% equity per position; 5 bps per side; one tick slippage; no dividends or short borrow",
            "history_status": "seen_history; selected on this same sample",
            "full": full, "longest_underwater": longest_underwater(curve),
            "calendar_years": years,
            "monthly_start_windows": windows,
            "window_note": "Overlapping monthly starts are sensitivity scenarios, not independent observations. Each window starts with fresh 1m RUB; indicators retain prior-bar warmup. Open positions are marked to the final close, with no exit fee."}


def main() -> None:
    bars = load_bars("SMLT", "1D")
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    tick = float(next(item["MINSTEP"] for item in universe if item["SECID"] == "SMLT"))
    report = analyze(bars, tick)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUT)
    print(json.dumps({key: {k: v for k, v in value.items() if k != "all"}
                      for key, value in report["monthly_start_windows"].items()},
                     ensure_ascii=False, indent=2))
    print("full", report["full"], "underwater", report["longest_underwater"])


if __name__ == "__main__":
    main()
