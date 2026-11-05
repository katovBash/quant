"""One read format for each independent paper account.

The durable state and event journal stay untouched. Consumers use this
projection so position, pending order and PnL mean the same thing everywhere.
"""

from __future__ import annotations


def account_record(status: dict, state: dict) -> dict:
    """Project a fleet status row and its durable state into a stable account row."""
    equity_log = state.get("equity_log") or []
    latest_equity = equity_log[-1] if equity_log else {}
    events = state.get("trades_log") or []
    latest_open = next((event for event in reversed(events)
                        if event.get("action") in ("OPEN_LONG", "OPEN_SHORT")), None)
    position = state.get("position", status.get("position", 0))
    equity = latest_equity.get("strategy_equity", state.get("initial_capital"))
    capital = state.get("initial_capital", status.get("initial_capital_rub"))
    mark_price = latest_equity.get("mark_price")
    entry_flow = state.get("entry_flow")
    open_pnl = (round(position * mark_price + (-entry_flow if position > 0 else entry_flow), 2)
                if position and isinstance(mark_price, (int, float))
                and isinstance(entry_flow, (int, float)) else 0 if not position else None)
    return {
        "account_id": status["account_id"],
        "symbol": status.get("symbol") or state.get("symbol"),
        "strategy": status.get("strategy") or state.get("strategy"),
        "timeframe": status.get("timeframe") or state.get("timeframe"),
        "status": status.get("status"), "paper_status": status.get("paper_status"),
        "source": status.get("source"), "error": status.get("error"),
        "last_completed_bar": status.get("last_completed_bar") or state.get("last_bar"),
        "position": position,
        "side": "LONG" if position > 0 else "SHORT" if position < 0 else "FLAT",
        "pending": status.get("pending") or state.get("pending"),
        "closed_trades": state.get("closed_trades", 0),
        "paper_gap_count": state.get("gap_count", 0),
        "started_at": state.get("started_at"),
        "equity": equity, "initial_capital": capital,
        "return_pct": round((equity / capital - 1) * 100, 3)
        if equity is not None and capital else None,
        "mark_price": mark_price,
        "open_pnl_rub": open_pnl,
        "open_pnl_pct": round(open_pnl / capital * 100, 4)
        if open_pnl is not None and capital else None,
        "entry_price": latest_open.get("price") if position and latest_open else None,
        "last_event": events[-1] if events else None,
        "position_weight_pct": status.get("position_weight_pct"),
        "orders_created": status.get("orders_created", 0),
        "new_events": status.get("new_events", 0),
    }
