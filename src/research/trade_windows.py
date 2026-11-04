"""Summarise consecutive closed-trade windows without a calendar-duration gate."""

from __future__ import annotations

from datetime import date


def trade_windows(trades: list[dict], size: int = 100, step: int = 1) -> list[dict]:
    if size < 1 or step < 1:
        raise ValueError("size and step must be positive")
    result = []
    for start in range(0, len(trades) - size + 1, step):
        window = trades[start:start + size]
        pnls = [float(trade["pnl_rub"]) for trade in window]
        wins = sum(pnl > 0 for pnl in pnls)
        gross_profit = sum(pnl for pnl in pnls if pnl > 0)
        gross_loss = -sum(pnl for pnl in pnls if pnl < 0)
        first = window[0]["entry_date"]
        last = window[-1]["exit_date"]
        result.append({"first_trade_number": start + 1,
                       "last_trade_number": start + size,
                       "first_entry_date": first,
                       "last_exit_date": last,
                       "elapsed_days": (date.fromisoformat(last) - date.fromisoformat(first)).days,
                       "closed_trades": size,
                       "winning_trades": wins,
                       "win_rate_pct": round(100 * wins / size, 2),
                       "pnl_rub": round(sum(pnls), 2),
                       "profit_factor": round(gross_profit / gross_loss, 3)
                       if gross_loss else ("inf" if gross_profit else 0.0)})
    return result
