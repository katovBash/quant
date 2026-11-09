"""Shared full-universe runner for preregistered trader-inspired OHLCV hypotheses."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars, source_path
from src.research.trader_method_signals import signals

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/candles/moex_scan"
FIELDS = ("symbol", "timeframe", "variant", "bars", "pnl_rub", "net_return_pct",
          "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct",
          "positive_months", "negative_months", "zero_months", "worst_month_pnl_rub")


def write_csv(path: Path, rows: list[dict], fields=None):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_regimes(output: Path, monthly: list[dict]) -> None:
    grouped = defaultdict(list)
    for item in monthly:
        grouped[(item["timeframe"], item["variant"], item["ex_post_regime"])].append(
            float(item["pnl_rub"]))
    rows = [{"timeframe": key[0], "variant": key[1], "ex_post_regime": key[2],
             "months": len(values), "profitable_months": sum(value > 0 for value in values),
             "median_month_pnl_rub": round(statistics.median(values), 2),
             "mean_month_pnl_rub": round(statistics.mean(values), 2)}
            for key, values in sorted(grouped.items())]
    write_csv(output / "monthly_regime_profiles.csv", rows,
              ("timeframe", "variant", "ex_post_regime", "months",
               "profitable_months", "median_month_pnl_rub", "mean_month_pnl_rub"))


def run(experiment: Path, *, smoke: bool = False, signal_factory=None,
        context_factory=None) -> dict:
    protocol = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
    output = experiment / ("smoke" if smoke else "results")
    output.mkdir(exist_ok=True)
    universe = json.loads((ROOT / protocol["eligible_universe"]["snapshot_file"]).read_text(encoding="utf-8"))
    symbols = sorted({item["SECID"] for item in universe if item["BOARDID"] == "TQBR"})
    if smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    variants = protocol["expected_variants"]
    method = protocol["method_id"]
    all_rows, all_monthly, all_yearly, skipped, errors = [], [], [], [], []
    (output / "manifest.json").write_text(json.dumps({
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": protocol["source_snapshot"], "symbols_attempted": len(symbols),
        "variants": variants, "timeframes": protocol["signal_timeframes"],
        "cost_status": protocol["cost_status"]}, ensure_ascii=False, indent=2) + "\n")
    for number, symbol in enumerate(symbols, 1):
        for timeframe in protocol["signal_timeframes"]:
            if not source_path(CACHE, symbol, timeframe).exists():
                skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "source_missing"})
                continue
            try:
                bars = load_research_bars(CACHE, symbol, timeframe)
                if len(bars) < protocol["min_bars"] or bars[-1]["ts"] < "2024-02-01":
                    skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "insufficient_bars"})
                    continue
                observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= protocol["start"]}
                gate = [True] * len(bars)
                active_factory = context_factory(symbol, timeframe) if context_factory else signal_factory
                for variant in variants:
                    if variant == "baseline":
                        entries, exits = signals("baseline", bars, 0)
                    elif active_factory is not None:
                        entries, exits = active_factory(variant, bars)
                    else:
                        lookback = int(variant.rsplit("_", 1)[1])
                        entries, exits = signals(method, bars, lookback)
                    curve, trades = [], []
                    result = simulate(bars, entries, gate, gate, 0.0, protocol["start"],
                                      fee_bps=protocol["simulator_cost_bps_per_side"],
                                      equity_curve=curve, trade_log=trades, exit_signals=exits)
                    monthly = [item for item in continuous_monthly_windows(
                        bars, curve, trades, 2024, protocol["split"])["all"]
                        if item["start"][:7] in observed]
                    if not monthly:
                        raise ValueError("no_complete_month_with_candles")
                    all_monthly.extend({"symbol": symbol, "timeframe": timeframe,
                                        "variant": variant, **item} for item in monthly)
                    years = defaultdict(list)
                    for item in monthly:
                        years[item["start"][:4]].append(item)
                    for year, items in years.items():
                        if len(items) == 12:
                            first, last = items[0]["starting_equity_rub"], items[-1]["ending_equity_rub"]
                            all_yearly.append({"symbol": symbol, "timeframe": timeframe,
                                               "variant": variant, "year": year,
                                               "return_pct": round(100 * (last / first - 1), 4) if first else None,
                                               "pnl_rub": round(last - first, 2),
                                               "closed_trades": sum(item["closed_trades"] for item in items)})
                    all_rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                                     "bars": len(bars), "pnl_rub": result["pnl_rub"],
                                     "net_return_pct": result["return_pct"],
                                     "closed_trades": result["closed_trades"],
                                     "winning_trades": result["winning_trades"],
                                     "profit_factor": result["profit_factor"],
                                     "max_drawdown_pct": result["max_drawdown_pct"],
                                     "positive_months": sum(item["pnl_rub"] > 0 for item in monthly),
                                     "negative_months": sum(item["pnl_rub"] < 0 for item in monthly),
                                     "zero_months": sum(item["pnl_rub"] == 0 for item in monthly),
                                     "worst_month_pnl_rub": min(item["pnl_rub"] for item in monthly)})
            except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": repr(exc)})
                skipped.append({"symbol": symbol, "timeframe": timeframe,
                                "reason": "calculation_error"})
        if number % 50 == 0 or number == len(symbols):
            print(f"{experiment.name}: {number}/{len(symbols)}, {len(all_rows)} rows", flush=True)
    if not all_rows:
        raise ValueError("no_evaluable_pairs")
    write_csv(output / "all_variants.csv", all_rows, FIELDS)
    write_csv(output / "monthly_returns.csv", all_monthly)
    write_regimes(output, all_monthly)
    write_csv(output / "yearly_returns.csv", all_yearly,
              ("symbol", "timeframe", "variant", "year", "return_pct", "pnl_rub", "closed_trades"))
    write_csv(output / "skipped.csv", skipped, ("symbol", "timeframe", "reason"))
    summary = {"cost_model": protocol["cost_status"], "errors": errors,
               "skipped": len(skipped), "symbols": len({item["symbol"] for item in all_rows}),
               "rows": len(all_rows), "months": len(all_monthly),
               "source_claim": "mechanical_interpretation; no verified personal trade journal"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    build_report(output, protocol, summary, all_rows, all_monthly)
    return summary
