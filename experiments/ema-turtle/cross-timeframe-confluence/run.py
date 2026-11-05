"""Frozen full-universe EMA25 first-touch and Turtle30/20 confluence test."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments/turtle/period-grid"))

from signals import buy_hold, prior_extrema, turtle_from_extrema
from src.ema.core.research_ema_combinations import simulate
from src.research.ema_turtle_combo import align_confirmed_events, recent_matching_gate, state_gate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.parameter_grid import variants_from_grid
from src.research.standalone_grid import ema_level_signals
from src.research.timeframes import load_research_bars, source_path

PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
CACHE = ROOT / PROTOCOL["eligible_universe"]["cache_dir"]
VARIANTS = PROTOCOL["expected_variants"]
FIELDS = ("symbol", "timeframe", "variant", "bars", "pnl_rub", "net_return_pct",
          "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct",
          "positive_months", "negative_months", "zero_months", "worst_month_pnl_rub")


def write_csv(path: Path, rows: list[dict], fields=None) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def variants_for(symbol: str, timeframe: str, bars: list[dict]):
    higher_timeframe = PROTOCOL["source_timeframe_map"][timeframe]["higher"]
    higher_bars = load_research_bars(CACHE, symbol, higher_timeframe)
    ema_same = ema_level_signals(bars, 25, 0.5)
    ema_higher = align_confirmed_events(
        higher_bars, ema_level_signals(higher_bars, 25, 0.5), bars,
        same_timeframe=False)
    extrema = prior_extrema(bars, {20, 30})
    turtle, turtle_exits = turtle_from_extrema(bars, 30, 20, extrema)
    hold, hold_exits = buy_hold(bars, PROTOCOL["start"])
    always = [True] * len(bars)
    rules = {"baseline": (hold, hold_exits, always, always),
             "turtle_only": (turtle, turtle_exits, always, always),
             "ema_only_same": (ema_same, [0] * len(bars), always, always),
             "ema_only_higher": (ema_higher, [0] * len(bars), always, always)}
    for label, ema_events in (("same", ema_same), ("higher", ema_higher)):
        up, down = state_gate(turtle, ema_events)
        rules[f"turtle_entry_ema_{label}"] = (turtle, turtle_exits, up, down)
        up, down = state_gate(ema_events, turtle)
        rules[f"ema_entry_turtle_{label}"] = (ema_events, [0] * len(bars), up, down)
        up, down = recent_matching_gate(turtle, ema_events, 3)
        rules[f"dual_event_3_{label}"] = (turtle, turtle_exits, up, down)
    return rules


def evaluate(symbol: str, timeframe: str, bars: list[dict]):
    rules = variants_for(symbol, timeframe, bars)
    observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= PROTOCOL["start"]}
    rows, months, years = [], [], []
    for variant in VARIANTS:
        entry, exits, gate_up, gate_down = rules[variant]
        curve, trades = [], []
        result = simulate(bars, entry, gate_up, gate_down, 0.0,
                          PROTOCOL["start"],
                          fee_bps=PROTOCOL["simulator_cost_bps_per_side"],
                          equity_curve=curve, trade_log=trades,
                          exit_signals=exits)
        monthly = [item for item in continuous_monthly_windows(
            bars, curve, trades, 2024, PROTOCOL["split"])["all"]
            if item["start"][:7] in observed]
        if not monthly:
            raise ValueError("no_complete_month_with_candles")
        months.extend({"symbol": symbol, "timeframe": timeframe,
                       "variant": variant, **item} for item in monthly)
        by_year = defaultdict(list)
        for item in monthly:
            by_year[item["start"][:4]].append(item)
        for year, items in by_year.items():
            if len(items) == 12:
                first, last = items[0]["starting_equity_rub"], items[-1]["ending_equity_rub"]
                years.append({"symbol": symbol, "timeframe": timeframe,
                              "variant": variant, "year": year,
                              "return_pct": round(100 * (last / first - 1), 4) if first else None,
                              "pnl_rub": round(last - first, 2),
                              "closed_trades": sum(item["closed_trades"] for item in items)})
        rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
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
    return rows, months, years


def run(*, smoke=False):
    generated = variants_from_grid(PROTOCOL["parameter_grid"])
    if generated != VARIANTS:
        raise ValueError(f"grid mismatch: {generated!r}")
    output = HERE / ("smoke" if smoke else "results")
    output.mkdir(exist_ok=True)
    universe = json.loads((ROOT / PROTOCOL["eligible_universe"]["snapshot_file"]).read_text())
    symbols = sorted({item["SECID"] for item in universe if item["BOARDID"] == "TQBR"})
    if smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    (output / "manifest.json").write_text(json.dumps({
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": PROTOCOL["source_snapshot"], "symbols_attempted": len(symbols),
        "variants": VARIANTS, "timeframes": PROTOCOL["signal_timeframes"],
        "cost_status": PROTOCOL["cost_status"]}, ensure_ascii=False, indent=2) + "\n")
    all_rows, all_monthly, all_yearly, skipped, errors = [], [], [], [], []
    for number, symbol in enumerate(symbols, 1):
        for timeframe in PROTOCOL["signal_timeframes"]:
            higher = PROTOCOL["source_timeframe_map"][timeframe]["higher"]
            if not source_path(CACHE, symbol, timeframe).exists() or not source_path(CACHE, symbol, higher).exists():
                skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "source_missing"})
                continue
            try:
                bars = load_research_bars(CACHE, symbol, timeframe)
                if len(bars) < PROTOCOL["min_bars"] or bars[-1]["ts"] < "2024-02-01":
                    skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "insufficient_bars"})
                    continue
                rows, months, years = evaluate(symbol, timeframe, bars)
                all_rows.extend(rows)
                all_monthly.extend(months)
                all_yearly.extend(years)
            except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": repr(exc)})
                skipped.append({"symbol": symbol, "timeframe": timeframe,
                                "reason": "calculation_error"})
        if number % 25 == 0 or number == len(symbols):
            print(f"EMA-Turtle: {number}/{len(symbols)}, {len(all_rows)} rows", flush=True)
    if not all_rows:
        raise ValueError("no_evaluable_pairs")
    write_csv(output / "all_variants.csv", all_rows, FIELDS)
    write_csv(output / "monthly_returns.csv", all_monthly)
    write_csv(output / "yearly_returns.csv", all_yearly,
              ("symbol", "timeframe", "variant", "year", "return_pct", "pnl_rub", "closed_trades"))
    write_csv(output / "skipped.csv", skipped, ("symbol", "timeframe", "reason"))
    grouped = defaultdict(list)
    for item in all_monthly:
        grouped[(item["timeframe"], item["variant"], item["ex_post_regime"])].append(float(item["pnl_rub"]))
    regimes = [{"timeframe": key[0], "variant": key[1], "ex_post_regime": key[2],
                "months": len(values), "profitable_months": sum(value > 0 for value in values),
                "median_month_pnl_rub": round(statistics.median(values), 2),
                "mean_month_pnl_rub": round(statistics.mean(values), 2)}
               for key, values in sorted(grouped.items())]
    write_csv(output / "monthly_regime_profiles.csv", regimes,
              ("timeframe", "variant", "ex_post_regime", "months", "profitable_months",
               "median_month_pnl_rub", "mean_month_pnl_rub"))
    summary = {"cost_model": PROTOCOL["cost_status"], "errors": errors,
               "skipped": len(skipped), "symbols": len({item["symbol"] for item in all_rows}),
               "rows": len(all_rows), "months": len(all_monthly),
               "source_claim": "combination of two historically selected indicator settings"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    build_report(output, PROTOCOL, summary, all_rows, all_monthly)
    return summary


if __name__ == "__main__":
    run(smoke="--smoke" in sys.argv)
