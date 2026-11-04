"""Run frozen weekly trendline / coarse volume profile grid across cached MOEX stocks."""

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

from levels import confluence, map_prior_week, rejection_signals, weekly_trendlines, weekly_volume_profile
from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.standalone_grid import atr, ema_level_signals
from src.research.timeframes import load_research_bars, source_path

HERE = Path(__file__).resolve().parent
CACHE = ROOT / "data/moex_scan"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
VARIANTS = PROTOCOL["variants"]
ROW_FIELDS = ("symbol", "timeframe", "variant", "bars", "pnl_rub", "net_return_pct",
              "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct",
              "positive_months", "negative_months", "zero_months", "worst_month_pnl_rub")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...] | None = None) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def evaluate(symbol: str, timeframe: str, daily: list[dict], bars: list[dict],
             trend_cache: dict, volume_cache: dict) -> tuple[list[dict], list[dict], list[dict]]:
    vol = atr(bars)
    baseline = ema_level_signals(bars, 25, 0.5)
    trend = {name: map_prior_week(bars, *trend_cache[name]) for name in ("small", "large")}
    profile = {weeks: map_prior_week(bars, *volume_cache[weeks]) for weeks in (26, 52)}
    level_sets = {
        "trend_small_2": trend["small"],
        "trend_large_2": trend["large"],
        "volume_26w": profile[26],
        "volume_52w": profile[52],
        "trend_small_volume_26w": confluence(trend["small"], profile[26], vol),
        "trend_large_volume_26w": confluence(trend["large"], profile[26], vol),
    }
    rows, monthly_rows, yearly_rows = [], [], []
    for variant in VARIANTS:
        signals = baseline if variant == "baseline" else rejection_signals(bars, level_sets[variant], vol)
        curve, trades = [], []
        result = simulate(bars, signals, [True] * len(bars), [True] * len(bars), 0,
                          PROTOCOL["start"], fee_bps=0, equity_curve=curve,
                          trade_log=trades, exit_signals=baseline)
        observed_months = {bar["ts"][:7] for bar in bars if bar["ts"] >= PROTOCOL["start"]}
        monthly = [item for item in continuous_monthly_windows(
            bars, curve, trades, 2024, PROTOCOL["split"])["all"]
            if item["start"][:7] in observed_months]
        for item in monthly:
            monthly_rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant, **item})
        by_year = defaultdict(list)
        for item in monthly:
            by_year[item["start"][:4]].append(item)
        for year, items in by_year.items():
            if len(items) == 12:
                first, last = items[0]["starting_equity_rub"], items[-1]["ending_equity_rub"]
                yearly_rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                                    "year": year, "return_pct": round(100 * (last / first - 1), 4),
                                    "pnl_rub": round(last - first, 2),
                                    "closed_trades": sum(x["closed_trades"] for x in items)})
        rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                     "bars": len(bars), "pnl_rub": result["pnl_rub"],
                     "net_return_pct": result["return_pct"],
                     "closed_trades": result["closed_trades"],
                     "winning_trades": result["winning_trades"],
                     "profit_factor": result["profit_factor"],
                     "max_drawdown_pct": result["max_drawdown_pct"],
                     "positive_months": sum(x["pnl_rub"] > 0 for x in monthly),
                     "negative_months": sum(x["pnl_rub"] < 0 for x in monthly),
                     "zero_months": sum(x["pnl_rub"] == 0 for x in monthly),
                     "worst_month_pnl_rub": min((x["pnl_rub"] for x in monthly), default=0)})
    return rows, monthly_rows, yearly_rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    output = HERE / ("smoke" if args.smoke else "results")
    output.mkdir(exist_ok=True)
    universe = json.loads((CACHE / "universe_2026-10-30.json").read_text())
    symbols = sorted(x["SECID"] for x in universe if x["BOARDID"] == "TQBR")
    if args.smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    all_rows, all_monthly, all_yearly, progress, errors, skipped = [], [], [], [], [], []
    manifest = {"started_utc": datetime.now(timezone.utc).isoformat(),
                "symbols": len(symbols), "variants": VARIANTS,
                "timeframes": PROTOCOL["signal_timeframes"], "snapshot": PROTOCOL["source_snapshot"],
                "cost_status": PROTOCOL["cost_status"]}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    for number, symbol in enumerate(symbols, 1):
        try:
            daily = load_research_bars(CACHE, symbol, "1D")
            if len(daily) < 34 or daily[-1]["ts"] < "2024-02-01":
                skipped.append({"symbol": symbol, "timeframe": "all", "reason": "no_evaluable_daily_history"})
                progress.append({"symbol": symbol, "index": number, "total": len(symbols),
                                 "status": "skipped", "error": "no_evaluable_daily_history"})
                continue
            trend_cache = {"small": weekly_trendlines(daily, 5, 2, 2),
                           "large": weekly_trendlines(daily, 25, 5, 2)}
            volume_cache = {26: weekly_volume_profile(daily, 26),
                            52: weekly_volume_profile(daily, 52)}
            for timeframe in PROTOCOL["signal_timeframes"]:
                if not source_path(CACHE, symbol, timeframe).exists():
                    skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "source_missing"})
                    continue
                bars = daily if timeframe == "1D" else load_research_bars(CACHE, symbol, timeframe)
                if len(bars) < 34 or bars[-1]["ts"] < "2024-02-01":
                    skipped.append({"symbol": symbol, "timeframe": timeframe,
                                    "reason": "no_evaluable_candles"})
                    continue
                rows, months, years = evaluate(symbol, timeframe, daily, bars, trend_cache, volume_cache)
                if not months:
                    skipped.append({"symbol": symbol, "timeframe": timeframe,
                                    "reason": "no_complete_month_with_candles"})
                    continue
                all_rows.extend(rows)
                all_monthly.extend(months)
                all_yearly.extend(years)
            progress.append({"symbol": symbol, "index": number, "total": len(symbols), "status": "ok"})
        except Exception as exc:
            errors.append({"symbol": symbol, "error": repr(exc)})
            progress.append({"symbol": symbol, "index": number, "total": len(symbols),
                             "status": "error", "error": repr(exc)})
        if number % 10 == 0 or number == len(symbols):
            write_csv(output / "progress.csv", progress, ("symbol", "index", "total", "status", "error"))
            print(f"{number}/{len(symbols)} symbols, {len(all_rows)} pairs, {len(errors)} errors", flush=True)
    write_csv(output / "all_variants.csv", all_rows, ROW_FIELDS)
    write_csv(output / "monthly_returns.csv", all_monthly)
    write_csv(output / "yearly_returns.csv", all_yearly)
    write_csv(output / "skipped.csv", skipped, ("symbol", "timeframe", "reason"))
    summary = {"cost_model": PROTOCOL["cost_status"], "errors": errors,
               "skipped": len(skipped),
               "symbols": len({x["symbol"] for x in all_rows}), "rows": len(all_rows),
               "positive_months": sum(x["pnl_rub"] > 0 for x in all_monthly),
               "months": len(all_monthly)}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    if all_rows:
        build_report(output, PROTOCOL, summary, all_rows, all_monthly)
    if not args.smoke:
        import subprocess
        command = [sys.executable, str(ROOT / "skills/new-experiment/scripts/check_coverage.py"),
                   str(output / "all_variants.csv"), "--timeframes", "1D", "1H", "4H",
                   "--monthly-csv", str(output / "monthly_returns.csv")]
        check = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (output / "coverage.json").write_text(check.stdout or check.stderr)
        print(f"coverage exit={check.returncode}", flush=True)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
