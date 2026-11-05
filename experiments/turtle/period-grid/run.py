"""Sweep frozen Turtle entry/exit windows on the same cached candles."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from signals import buy_hold, prior_extrema, turtle_from_extrema
from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars, source_path

HERE = Path(__file__).resolve().parent
CACHE = ROOT / "data/candles/moex_scan"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
PAIRS = [(entry, exit_length) for entry in PROTOCOL["entry_lengths"]
         for exit_length in PROTOCOL["exit_lengths"] if exit_length < entry]
VARIANTS = ["baseline"] + [f"dennis_turtle_{entry}_{exit_length}"
                            for entry, exit_length in PAIRS]
ROW_FIELDS = ("symbol", "timeframe", "variant", "bars", "pnl_rub", "net_return_pct",
              "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct",
              "positive_months", "negative_months", "zero_months", "worst_month_pnl_rub")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def trade_windows(symbol: str, timeframe: str, variant: str, trades: list[dict]) -> list[dict]:
    if len(trades) < 100:
        return []
    prefix_pnl = [0.0]
    prefix_wins = [0]
    for trade in trades:
        prefix_pnl.append(prefix_pnl[-1] + trade["pnl_rub"])
        prefix_wins.append(prefix_wins[-1] + (trade["pnl_rub"] > 0))
    return [{"symbol": symbol, "timeframe": timeframe, "variant": variant,
             "first_trade_number": end - 98, "last_trade_number": end + 1,
             "closed_trades": 100, "first_entry_date": trades[end - 99]["entry_date"],
             "last_exit_date": trades[end]["exit_date"],
             "pnl_rub": round(prefix_pnl[end + 1] - prefix_pnl[end - 99], 2),
             "winning_trades": prefix_wins[end + 1] - prefix_wins[end - 99]}
            for end in range(99, len(trades))]


def evaluate(symbol: str, timeframe: str, bars: list[dict],
             dividends_per_share: dict[str, float] | None = None) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    extrema = prior_extrema(bars, set(PROTOCOL["entry_lengths"] + PROTOCOL["exit_lengths"]))
    pairs = {"baseline": buy_hold(bars, PROTOCOL["start"])}
    pairs.update({f"dennis_turtle_{entry}_{exit_length}":
                  turtle_from_extrema(bars, entry, exit_length, extrema)
                  for entry, exit_length in PAIRS})
    monthly_observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= PROTOCOL["start"]}
    rows, monthly_rows, yearly_rows, window_rows = [], [], [], []
    gate = [True] * len(bars)
    for variant in VARIANTS:
        signals, exits = pairs[variant]
        curve, trades = [], []
        result = simulate(bars, signals, gate, gate, 0.0, PROTOCOL["start"],
                          fee_bps=PROTOCOL["simulator_cost_bps_per_side"],
                          dividends_per_share=dividends_per_share,
                          equity_curve=curve, trade_log=trades,
                          exit_signals=exits)
        monthly = [item for item in continuous_monthly_windows(
            bars, curve, trades, 2024, PROTOCOL["split"])["all"]
            if item["start"][:7] in monthly_observed]
        if not monthly:
            raise ValueError("no_complete_month_with_candles")
        monthly_rows.extend({"symbol": symbol, "timeframe": timeframe,
                             "variant": variant, **item} for item in monthly)
        by_year = defaultdict(list)
        for item in monthly:
            by_year[item["start"][:4]].append(item)
        for year, items in by_year.items():
            if len(items) == 12:
                first, last = items[0]["starting_equity_rub"], items[-1]["ending_equity_rub"]
                yearly_rows.append({"symbol": symbol, "timeframe": timeframe,
                                    "variant": variant, "year": year,
                                    "return_pct": round(100 * (last / first - 1), 4) if first else None,
                                    "pnl_rub": round(last - first, 2),
                                    "closed_trades": sum(item["closed_trades"] for item in items)})
        window_rows.extend(trade_windows(symbol, timeframe, variant, trades))
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
    return rows, monthly_rows, yearly_rows, window_rows


def write_regimes(path: Path, monthly: list[dict]) -> None:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in monthly:
        groups[(item["timeframe"], item["variant"], item["ex_post_regime"])].append(item)
    rows = []
    for (timeframe, variant, regime), items in sorted(groups.items()):
        pnls = [float(item["pnl_rub"]) for item in items]
        rows.append({"timeframe": timeframe, "variant": variant, "ex_post_regime": regime,
                     "months": len(items), "profitable_months": sum(value > 0 for value in pnls),
                     "median_month_pnl_rub": round(statistics.median(pnls), 2),
                     "mean_month_pnl_rub": round(statistics.mean(pnls), 2)})
    write_csv(path, rows, ("timeframe", "variant", "ex_post_regime", "months",
                           "profitable_months", "median_month_pnl_rub", "mean_month_pnl_rub"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    output = HERE / ("smoke" if args.smoke else "results")
    output.mkdir(exist_ok=True)
    universe = json.loads((CACHE / "universe_2026-10-30.json").read_text(encoding="utf-8"))
    symbols = sorted(x["SECID"] for x in universe if x["BOARDID"] == "TQBR"
                     and source_path(CACHE, x["SECID"], "1D").exists()
                     and source_path(CACHE, x["SECID"], "1H").exists())
    if args.smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    (output / "manifest.json").write_text(json.dumps({
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": PROTOCOL["source_snapshot"],
        "symbols_attempted": len(symbols), "variants": VARIANTS,
        "timeframes": PROTOCOL["signal_timeframes"],
        "cost_status": PROTOCOL["cost_status"]}, ensure_ascii=False, indent=2))
    all_rows, all_monthly, all_yearly, all_windows = [], [], [], []
    progress, skipped, errors = [], [], []
    for number, symbol in enumerate(symbols, 1):
        try:
            daily = load_research_bars(CACHE, symbol, "1D")
            if len(daily) < max(PROTOCOL["entry_lengths"]) + 34 or daily[-1]["ts"] < "2024-02-01":
                skipped.append({"symbol": symbol, "timeframe": "all", "reason": "no_evaluable_daily_history"})
                progress.append({"symbol": symbol, "index": number, "total": len(symbols),
                                 "status": "skipped", "error": "no_evaluable_daily_history"})
            else:
                for timeframe in PROTOCOL["signal_timeframes"]:
                    if not source_path(CACHE, symbol, timeframe).exists():
                        skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "source_missing"})
                        continue
                    bars = daily if timeframe == "1D" else load_research_bars(CACHE, symbol, timeframe)
                    if len(bars) < max(PROTOCOL["entry_lengths"]) + 34 or bars[-1]["ts"] < "2024-02-01":
                        skipped.append({"symbol": symbol, "timeframe": timeframe,
                                        "reason": "no_evaluable_candles"})
                        continue
                    try:
                        rows, months, years, windows = evaluate(symbol, timeframe, bars)
                    except Exception as exc:
                        errors.append({"symbol": symbol, "timeframe": timeframe, "error": repr(exc)})
                        skipped.append({"symbol": symbol, "timeframe": timeframe,
                                        "reason": "calculation_error"})
                        continue
                    all_rows.extend(rows)
                    all_monthly.extend(months)
                    all_yearly.extend(years)
                    all_windows.extend(windows)
                progress.append({"symbol": symbol, "index": number, "total": len(symbols),
                                 "status": "ok", "error": ""})
        except Exception as exc:
            errors.append({"symbol": symbol, "timeframe": "all", "error": repr(exc)})
            progress.append({"symbol": symbol, "index": number, "total": len(symbols),
                             "status": "error", "error": repr(exc)})
        if number % 10 == 0 or number == len(symbols):
            write_csv(output / "progress.csv", progress, ("symbol", "index", "total", "status", "error"))
            print(f"{number}/{len(symbols)} symbols, {len(all_rows)} pairs, {len(errors)} errors", flush=True)
    write_csv(output / "all_variants.csv", all_rows, ROW_FIELDS)
    write_csv(output / "monthly_returns.csv", all_monthly)
    write_csv(output / "yearly_returns.csv", all_yearly,
              ("symbol", "timeframe", "variant", "year", "return_pct", "pnl_rub", "closed_trades"))
    write_csv(output / "trade_windows_100.csv", all_windows,
              ("symbol", "timeframe", "variant", "first_trade_number", "last_trade_number",
               "closed_trades", "first_entry_date", "last_exit_date", "pnl_rub", "winning_trades"))
    write_csv(output / "skipped.csv", skipped, ("symbol", "timeframe", "reason"))
    write_regimes(output / "monthly_regime_profiles.csv", all_monthly)
    summary = {"cost_model": PROTOCOL["cost_status"], "errors": errors,
               "skipped": len(skipped), "symbols": len({item["symbol"] for item in all_rows}),
               "rows": len(all_rows), "months": len(all_monthly),
               "trade_windows_100": len(all_windows)}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    if all_rows:
        build_report(output, PROTOCOL, summary, all_rows, all_monthly)
    if not args.smoke:
        import subprocess
        command = [sys.executable, str(ROOT / "skills/new-experiment/scripts/check_coverage.py"),
                   str(output / "all_variants.csv"), "--timeframes", *PROTOCOL["signal_timeframes"],
                   "--monthly-csv", str(output / "monthly_returns.csv"),
                   "--trade-windows-csv", str(output / "trade_windows_100.csv")]
        check = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (output / "coverage.json").write_text(check.stdout or check.stderr)
        print(f"coverage exit={check.returncode}", flush=True)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
