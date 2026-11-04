"""Causal efficiency-ratio filter and calendar-month backtest diagnostics."""

from __future__ import annotations

import math
import statistics
from bisect import bisect_left
from datetime import date

from src.ema.core.research_ema_combinations import simulate


def efficiency_ratio(closes: list[float], length: int) -> list[float]:
    """Absolute L-bar displacement divided by path length through the current bar."""
    if length < 2:
        raise ValueError("length must be at least 2")
    result = [math.nan] * len(closes)
    path = 0.0
    for i in range(1, len(closes)):
        path += abs(closes[i] - closes[i - 1])
        if i > length:
            path -= abs(closes[i - length] - closes[i - length - 1])
        if i >= length:
            result[i] = abs(closes[i] - closes[i - length]) / path if path > 0 else 0.0
    return result


def monthly_windows(bars: list[dict], signals: list[int], gate: list[bool],
                    tick: float, first_year: int, split: str,
                    gate_down: list[bool] | None = None,
                    exit_signals: list[int] | None = None,
                    fee_bps: float = 5) -> dict:
    """Fresh 1m RUB account for each complete calendar month; prior signals stay warm."""
    dates = [bar["ts"][:10] for bar in bars]
    gate_down = gate if gate_down is None else gate_down
    final = date.fromisoformat(dates[-1])
    rows = []
    year, month = first_year, 1
    while True:
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1)
        if end > final:
            break
        first_idx = bisect_left(dates, start.isoformat())
        end_idx = bisect_left(dates, end.isoformat())
        prefix = max(0, first_idx - 33)
        result = simulate(bars[prefix:end_idx], signals[prefix:end_idx],
                          gate[prefix:end_idx], gate_down[prefix:end_idx], tick,
                          start.isoformat(), end.isoformat(),
                          exit_signals=exit_signals[prefix:end_idx] if exit_signals is not None else None,
                          fee_bps=fee_bps)
        if first_idx < end_idx:
            market_return = 100 * (bars[end_idx-1]["close"] / bars[first_idx]["open"] - 1)
            market_range = 100 * (max(bar["high"] for bar in bars[first_idx:end_idx])
                                  - min(bar["low"] for bar in bars[first_idx:end_idx])) / bars[first_idx]["open"]
            regime = ("growth" if market_return > 5 else
                      "decline" if market_return < -5 else
                      "sideways" if market_range <= 10 else "volatile_mixed")
        else:
            market_return = market_range = math.nan
            regime = "no_data"
        rows.append({"start": start.isoformat(), "end_exclusive": end.isoformat(),
                     "sample": "train" if end.isoformat() <= split else "late_seen_history",
                     "return_pct": result["return_pct"],
                     "pnl_rub": result["pnl_rub"],
                     "closed_trades": result["closed_trades"],
                     "winning_trades": result["winning_trades"],
                     "win_rate_pct": round(100 * result["winning_trades"] / result["closed_trades"], 2)
                                     if result["closed_trades"] else None,
                     "max_drawdown_pct": result["max_drawdown_pct"],
                     "market_return_pct": round(market_return, 2),
                     "market_range_pct": round(market_range, 2),
                     "ex_post_regime": regime})
        year, month = end.year, end.month
    return {"all": rows, "count": len(rows),
            "negative_count": sum(row["return_pct"] < 0 for row in rows),
            "nonpositive_count": sum(row["return_pct"] <= 0 for row in rows),
            "zero_trade_count": sum(row["closed_trades"] == 0 for row in rows),
            "worst": min(rows, key=lambda row: row["return_pct"]) if rows else None,
            "median_return_pct": round(statistics.median(row["return_pct"] for row in rows), 2)
                                 if rows else None}


def continuous_monthly_windows(bars: list[dict], equity_curve: list[dict],
                               trades: list[dict], first_year: int, split: str,
                               initial_capital: float = 1_000_000) -> dict:
    """Month-end changes of one continuously running, marked-to-market account."""
    dates = [bar["ts"][:10] for bar in bars]
    curve_dates = [item["date"] for item in equity_curve]
    trade_dates = [item["exit_date"] for item in trades]
    final = date.fromisoformat(dates[-1])
    rows = []
    previous_equity = initial_capital
    year, month = first_year, 1
    while True:
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1)
        if end > final:
            break
        first_idx = bisect_left(dates, start.isoformat())
        end_idx = bisect_left(dates, end.isoformat())
        curve_start = bisect_left(curve_dates, start.isoformat())
        curve_end = bisect_left(curve_dates, end.isoformat())
        month_curve = [item["equity"] for item in equity_curve[curve_start:curve_end]]
        ending_equity = month_curve[-1] if month_curve else previous_equity
        pnl = ending_equity - previous_equity
        peak = previous_equity
        drawdown = 0.0
        for equity in month_curve:
            peak = max(peak, equity)
            drawdown = min(drawdown, equity / peak - 1)
        trade_start = bisect_left(trade_dates, start.isoformat())
        trade_end = bisect_left(trade_dates, end.isoformat())
        closed = trades[trade_start:trade_end]
        wins = sum(item["pnl_rub"] > 0 for item in closed)
        if first_idx < end_idx:
            market_return = 100 * (bars[end_idx-1]["close"] / bars[first_idx]["open"] - 1)
            market_range = 100 * (max(bar["high"] for bar in bars[first_idx:end_idx])
                                  - min(bar["low"] for bar in bars[first_idx:end_idx])) / bars[first_idx]["open"]
            regime = ("growth" if market_return > 5 else
                      "decline" if market_return < -5 else
                      "sideways" if market_range <= 10 else "volatile_mixed")
        else:
            market_return = market_range = math.nan
            regime = "no_data"
        rows.append({"start": start.isoformat(), "end_exclusive": end.isoformat(),
                     "sample": "train" if end.isoformat() <= split else "late_seen_history",
                     "starting_equity_rub": round(previous_equity, 2),
                     "ending_equity_rub": round(ending_equity, 2),
                     "return_pct": round(100 * pnl / previous_equity, 4),
                     "pnl_rub": round(pnl, 2),
                     "closed_trades": len(closed), "winning_trades": wins,
                     "win_rate_pct": round(100 * wins / len(closed), 2) if closed else None,
                     "max_drawdown_pct": round(100 * drawdown, 2),
                     "market_return_pct": round(market_return, 2),
                     "market_range_pct": round(market_range, 2),
                     "ex_post_regime": regime})
        previous_equity = ending_equity
        year, month = end.year, end.month
    return {"kind": "continuous_marked_to_market", "all": rows, "count": len(rows),
            "negative_count": sum(row["pnl_rub"] < 0 for row in rows),
            "nonpositive_count": sum(row["pnl_rub"] <= 0 for row in rows),
            "zero_trade_count": sum(row["closed_trades"] == 0 for row in rows),
            "worst": min(rows, key=lambda row: row["pnl_rub"]) if rows else None,
            "median_return_pct": round(statistics.median(row["return_pct"] for row in rows), 2)
                                 if rows else None}


def calendar_year_windows(bars: list[dict], signals: list[int], gate: list[bool],
                          tick: float, first_year: int,
                          gate_down: list[bool] | None = None,
                          exit_signals: list[int] | None = None,
                          fee_bps: float = 5) -> list[dict]:
    """Yearly fresh-account returns with ex-post stock direction for diagnostics only."""
    gate_down = gate if gate_down is None else gate_down
    dates = [bar["ts"][:10] for bar in bars]
    final = date.fromisoformat(dates[-1])
    rows = []
    for year in range(first_year, final.year + 1):
        start, end = date(year, 1, 1), date(year + 1, 1, 1)
        first_idx = bisect_left(dates, start.isoformat())
        end_idx = bisect_left(dates, end.isoformat())
        if first_idx == end_idx:
            continue
        prefix = max(0, first_idx - 33)
        result = simulate(bars[prefix:end_idx], signals[prefix:end_idx],
                          gate[prefix:end_idx], gate_down[prefix:end_idx], tick,
                          start.isoformat(), end.isoformat(),
                          exit_signals=exit_signals[prefix:end_idx] if exit_signals is not None else None,
                          fee_bps=fee_bps)
        underlying = 100 * (bars[end_idx-1]["close"] / bars[first_idx]["open"] - 1)
        year_range = 100 * (max(bar["high"] for bar in bars[first_idx:end_idx])
                            - min(bar["low"] for bar in bars[first_idx:end_idx])) / bars[first_idx]["open"]
        observed_dates = set(dates[first_idx:end_idx])
        complete = (end <= final and date.fromisoformat(dates[first_idx]).month == 1
                    and date.fromisoformat(dates[end_idx-1]).month == 12
                    and len(observed_dates) >= 150)
        regime = ("growth" if underlying > 10 else
                  "decline" if underlying < -10 else
                  "sideways" if year_range <= 30 else "volatile_mixed")
        rows.append({"year": year, "partial": not complete,
                     "return_pct": result["return_pct"],
                     "pnl_rub": result["pnl_rub"],
                     "closed_trades": result["closed_trades"],
                     "winning_trades": result["winning_trades"],
                     "win_rate_pct": round(100 * result["winning_trades"] / result["closed_trades"], 2)
                                     if result["closed_trades"] else None,
                     "underlying_return_pct": round(underlying, 2),
                     "market_range_pct": round(year_range, 2),
                     "ex_post_regime": regime})
    return rows
