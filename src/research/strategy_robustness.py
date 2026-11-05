"""Recalculate monthly start-date risk for every selected strategy and symbol."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
from bisect import bisect_left
from datetime import date, timedelta
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate
from src.ema.core.scan_ema import ema
from src.ema.core.compare_ema_filters import rsi
from src.research.indicator_library import crosses, signal_series, specifications
from src.research.standalone_grid import (CACHE, UNIVERSE, adx_direction,
                                          ema_level_signals, four_point_signals,
                                          load_bars, pattern_signals)
from src.research.timeframes import sample_period

ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ROOT / "strategies"
WINDOWS_MONTHS = (1, 6, 12, 24)
WINDOWS_DAYS = (7, 14)


def add_months(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def strategy_signals(strategy_id: str, selection: dict, bars: list[dict]) -> list[int]:
    match = re.fullmatch(r"ema-cross-(\d+)-(\d+)-long-short-1h", strategy_id)
    if match:
        closes = [bar["close"] for bar in bars]
        return crosses(ema(closes, int(match[1])), ema(closes, int(match[2])))
    match = re.fullmatch(r"ema-level-(\d+)-atr(\d+)-long-short-(?:1h|1d)", strategy_id)
    if match:
        width = int(match[2]) / (10 ** (len(match[2]) - 1))
        return ema_level_signals(bars, int(match[1]), width)
    if strategy_id == "rsi-21-60-40-long-short-1h":
        values = rsi(bars, 21)
        result = [0] * len(values)
        for i in range(1, len(values)):
            if math.isfinite(values[i-1]) and math.isfinite(values[i]):
                if values[i-1] <= 60 < values[i]:
                    result[i] = 1
                elif values[i-1] >= 40 > values[i]:
                    result[i] = -1
        return result
    if strategy_id == "adx-di-14-20-long-short-1h":
        return adx_direction(bars, 14, 20)
    if strategy_id == "four-point-levels-5-1p5-long-short-1h":
        return four_point_signals(bars, 5, 1.5)
    if strategy_id == "breakout-20-long-short-1h":
        return pattern_signals(bars, "breakout", 20)
    if strategy_id == "sma-cross-10-59-atr025-long-short-1h":
        path = STRATEGIES / strategy_id / "strategy.py"
        spec = importlib.util.spec_from_file_location("selected_sma_atr", path)
        if spec is None or spec.loader is None:
            raise ValueError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.signal_series(bars)
    selector = selection.get("selector") or {}
    rule_id = selector.get("rule_id")
    if rule_id:
        indicator_spec = next((item for item in specifications() if item["rule_id"] == rule_id), None)
        if indicator_spec is None:
            raise ValueError(f"unknown rule_id: {rule_id}")
        return signal_series(bars, indicator_spec)
    raise ValueError(f"no fixed signal adapter for {strategy_id}")


def underwater(curve: list[dict]) -> dict:
    peak = 1_000_000.0
    start = None
    worst = {"calendar_days": 0, "start": None, "end": None, "recovered": True}
    for point in curve:
        day = date.fromisoformat(point["date"])
        if point["equity"] >= peak:
            peak = point["equity"]
            if start is not None:
                candidate = {"calendar_days": (day-start).days, "start": start.isoformat(),
                             "end": day.isoformat(), "recovered": True}
                if candidate["calendar_days"] > worst["calendar_days"]:
                    worst = candidate
                start = None
        elif start is None:
            start = day
    if start is not None:
        day = date.fromisoformat(curve[-1]["date"])
        candidate = {"calendar_days": (day-start).days, "start": start.isoformat(),
                     "end": day.isoformat(), "recovered": False}
        if candidate["calendar_days"] > worst["calendar_days"]:
            worst = candidate
    return worst


def analyze_pair(strategy_id: str, selection: dict, symbol: str, tick: float) -> dict:
    timeframe = selection["timeframe"]
    bars = load_bars(symbol, timeframe)
    if len(bars) < 250:
        raise ValueError(f"insufficient_bars:{len(bars)}")
    signals = strategy_signals(strategy_id, selection, bars)
    allowed = [True] * len(bars)
    start_text, _ = sample_period(timeframe)
    curve: list[dict] = []
    full = simulate(bars, signals, allowed, allowed, tick, start_text, equity_curve=curve)
    last_day = date.fromisoformat(bars[-1]["ts"][:10])
    dates = [bar["ts"][:10] for bar in bars]

    def window_result(start: date, end: date) -> dict:
        first = bisect_left(dates, start.isoformat())
        last = bisect_left(dates, end.isoformat())
        prefix = max(0, first - 33)
        return simulate(bars[prefix:last], signals[prefix:last],
                        allowed[prefix:last], allowed[prefix:last], tick,
                        start.isoformat(), end.isoformat())

    def describe_window(start: date, end: date) -> dict:
        result = window_result(start, end)
        return {"start": start.isoformat(), "end_exclusive": end.isoformat(),
                "return_pct": result["return_pct"],
                "closed_trades": result["closed_trades"],
                "max_drawdown_pct": result["max_drawdown_pct"]}

    def summarize(rows: list[dict]) -> dict:
        return {"count": len(rows),
                "negative_count": sum(row["return_pct"] < 0 for row in rows),
                "zero_trade_count": sum(row["closed_trades"] == 0 for row in rows),
                "worst": min(rows, key=lambda row: row["return_pct"]) if rows else None,
                "best": max(rows, key=lambda row: row["return_pct"]) if rows else None,
                "all": rows}

    weekly = {}
    for days in WINDOWS_DAYS:
        rows = []
        start = date.fromisoformat(start_text)
        while start + timedelta(days=days) <= last_day:
            rows.append(describe_window(start, start + timedelta(days=days)))
            start += timedelta(days=7)
        weekly[str(days)] = summarize(rows)
    windows = {}
    for months in WINDOWS_MONTHS:
        rows = []
        start = date.fromisoformat(start_text)
        while add_months(start, months) <= last_day:
            end = add_months(start, months)
            rows.append(describe_window(start, end))
            start = add_months(start, 1)
        windows[str(months)] = summarize(rows)
    years = []
    for year in range(date.fromisoformat(start_text).year, last_day.year + 1):
        begin, end = date(year, 1, 1), date(year+1, 1, 1)
        result = window_result(begin, end)
        years.append({"year": year, "partial": end > last_day,
                      "return_pct": result["return_pct"],
                      "closed_trades": result["closed_trades"]})
    return {"symbol": symbol, "timeframe": timeframe, "first_bar": bars[0]["ts"],
            "last_bar": bars[-1]["ts"], "full": full,
            "longest_underwater": underwater(curve),
            "weekly_start_windows_days": weekly,
            "monthly_start_windows": windows, "calendar_years": years}


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", action="append", help="limit to one or more strategy ids")
    args = parser.parse_args(argv)
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    ticks = {item["SECID"]: float(item.get("MINSTEP") or 0) for item in universe}
    summary = {"snapshot": "2026-10-30", "history_status": "seen_history",
               "model": "fixed signals, next-open fills, 25% equity, 5 bps fee per side, one tick slip; excludes dividends, borrow cost, lots and corporate actions",
               "interpretation": "Weekly starts for 7/14-day windows and monthly starts for 1/6/12/24-month windows are risk scenarios, not independent probabilities. Short windows may have zero closed trades. This is historical diagnosis, not paper approval. Windows reset to 1m RUB; open positions marked to final close without exit fee.",
               "strategies": [], "errors": []}
    for path in sorted(STRATEGIES.glob("*/selection.json")):
        selection = json.loads(path.read_text(encoding="utf-8"))
        strategy_id = selection["id"]
        if args.strategy and strategy_id not in args.strategy:
            continue
        symbols = sorted(set(selection.get("active_paper_symbols", [])) |
                         {item["symbol"] for item in selection.get("top10", [])})
        report = {"strategy_id": strategy_id, "timeframe": selection["timeframe"],
                  "snapshot": "2026-10-30", "model": summary["model"],
                  "history_status": "seen_history", "pairs": [], "errors": []}
        for symbol in symbols:
            try:
                pair = analyze_pair(strategy_id, selection, symbol, ticks[symbol])
                report["pairs"].append(pair)
                print(strategy_id, symbol, pair["full"]["return_pct"],
                      pair["monthly_start_windows"]["24"]["worst"], flush=True)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                error = {"strategy_id": strategy_id, "symbol": symbol, "error": str(exc)}
                report["errors"].append(error)
                summary["errors"].append(error)
                print("ERROR", error, flush=True)
        output = path.parent / "robustness.json"
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary["strategies"].append({"id": strategy_id, "timeframe": selection["timeframe"],
            "symbols": len(symbols), "calculated": len(report["pairs"]),
            "errors": len(report["errors"]),
            "negative_7d": sum(bool(pair["weekly_start_windows_days"]["7"]["negative_count"])
                                for pair in report["pairs"]),
            "negative_14d": sum(bool(pair["weekly_start_windows_days"]["14"]["negative_count"])
                                 for pair in report["pairs"]),
            "negative_1m": sum(bool(pair["monthly_start_windows"]["1"]["negative_count"])
                                for pair in report["pairs"]),
            "negative_24m": sum(bool(pair["monthly_start_windows"]["24"]["negative_count"])
                                for pair in report["pairs"]),
            "underwater_365d": sum(pair["longest_underwater"]["calendar_days"] >= 365
                                   for pair in report["pairs"]),
            "report": str(output.relative_to(ROOT))})
    summary["totals"] = {key: sum(item[key] for item in summary["strategies"])
                         for key in ("symbols", "calculated", "errors", "negative_7d",
                                     "negative_14d", "negative_1m", "negative_24m",
                                     "underwater_365d")}
    if summary["strategies"]:
        (STRATEGIES / "robustness.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()
