"""Recalculate long-only and short-only outcomes for selected research examples."""

from __future__ import annotations

import json
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars
from src.research.trader_method_run import ROOT, write_csv
from src.research.trader_method_signals import signals

AUTHORS = {"john-bollinger", "brian-shannon", "alexander-gerchik",
           "alexander-elder", "william-oneil"}
FIELDS = ("symbol", "timeframe", "variant", "mode", "long_closed", "long_wins",
          "short_closed", "short_wins", "return_pct", "profitable_months",
          "months", "conclusion")


def build(experiment: Path) -> int:
    protocol = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
    results = experiment / "results"
    review = json.loads((results / "paper_review.json").read_text(encoding="utf-8"))
    rule = review.get("rule") or {}
    variant = rule.get("variant")
    timeframe = rule.get("timeframe")
    if not variant or not timeframe:
        return 0
    lookback = int(variant.rsplit("_", 1)[1])
    rows = []
    for stock in review.get("stocks", []):
        symbol = stock["symbol"]
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, timeframe)
        entry, exits = signals(protocol["method_id"], bars, lookback)
        for mode in ("long_only", "short_only"):
            up = [mode == "long_only"] * len(bars)
            down = [mode == "short_only"] * len(bars)
            curve, trades = [], []
            outcome = simulate(bars, entry, up, down, 0.0, protocol["start"],
                               fee_bps=protocol["simulator_cost_bps_per_side"],
                               equity_curve=curve, trade_log=trades, exit_signals=exits)
            months = continuous_monthly_windows(bars, curve, trades, 2024, protocol["split"])["all"]
            rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                         "mode": mode,
                         "long_closed": sum(t["side"] == "long" for t in trades),
                         "long_wins": sum(t["side"] == "long" and t["pnl_rub"] > 0 for t in trades),
                         "short_closed": sum(t["side"] == "short" for t in trades),
                         "short_wins": sum(t["side"] == "short" and t["pnl_rub"] > 0 for t in trades),
                         "return_pct": outcome["return_pct"],
                         "profitable_months": sum(m["pnl_rub"] > 0 for m in months),
                         "months": len(months),
                         "conclusion": "diagnostic_only; selected examples, not whole grid"})
    write_csv(results / "trade_side_summary.csv", rows, FIELDS)
    return len(rows)


def main() -> None:
    for author in sorted(AUTHORS):
        for protocol in sorted((ROOT / "experiments" / author).glob("*/protocol.json")):
            print(protocol.parent.relative_to(ROOT), build(protocol.parent), flush=True)


if __name__ == "__main__":
    main()
