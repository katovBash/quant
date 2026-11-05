"""Full fixed-grid test of a close-confirmed Turtle Soup adaptation."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.parameter_grid import variants_from_grid
from src.research.timeframes import load_research_bars, source_path

HERE = Path(__file__).resolve().parent
CACHE = ROOT / "data/candles/moex_scan"
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
VARIANTS = variants_from_grid(PROTOCOL["parameter_grid"])
LOOKBACKS = PROTOCOL["parameter_grid"]["axes"]["lookback"]["values"]
SEPARATIONS = PROTOCOL["parameter_grid"]["axes"]["separation"]["values"]
HOLDS = PROTOCOL["parameter_grid"]["axes"]["hold"]["values"]
ROW_FIELDS = ("symbol", "timeframe", "variant", "bars", "pnl_rub", "net_return_pct",
              "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct",
              "positive_months", "negative_months", "zero_months", "worst_month_pnl_rub")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...] | None = None) -> None:
    if not rows and not fields:
        raise ValueError(f"empty table needs explicit fields: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prior_levels(bars: list[dict], lookback: int) -> list[tuple[float, int, float, int] | None]:
    """Price and most recent index of each extreme, using only earlier candles."""
    levels: list[tuple[float, int, float, int] | None] = [None] * len(bars)
    for i in range(lookback, len(bars)):
        window = range(i - lookback, i)
        low_index = min(window, key=lambda j: (bars[j]["low"], -j))
        high_index = max(window, key=lambda j: (bars[j]["high"], j))
        levels[i] = (bars[low_index]["low"], low_index,
                     bars[high_index]["high"], high_index)
    return levels


def signals_for(bars: list[dict], levels: list[tuple[float, int, float, int] | None],
                separation: int, hold: int) -> tuple[list[int], list[int]]:
    signals = [0] * len(bars)
    exits = [0] * len(bars)
    locked_until = -1
    for i, bar in enumerate(bars):
        if i == locked_until:
            exits[i] = -signals[locked_until - hold]
            continue
        if i < locked_until or levels[i] is None:
            continue
        prior_low, low_index, prior_high, high_index = levels[i]
        long = bar["low"] < prior_low < bar["close"] and i - low_index >= separation
        short = bar["high"] > prior_high > bar["close"] and i - high_index >= separation
        direction = 1 if long and not short else -1 if short and not long else 0
        if direction:
            signals[i] = direction
            locked_until = i + hold
    return signals, exits


def evaluate(symbol: str, timeframe: str, bars: list[dict]) -> tuple[list[dict], list[dict]]:
    levels = {lookback: prior_levels(bars, lookback) for lookback in LOOKBACKS}
    base = [0] * len(bars)
    baseline_entry = next((i for i in range(33, len(bars))
                           if bars[i]["ts"][:10] >= PROTOCOL["start"]), None)
    if baseline_entry is None:
        raise ValueError("no_bar_after_start")
    base[baseline_entry - 1] = 1
    signals = {"baseline": (base, [0] * len(bars))}
    for lookback in LOOKBACKS:
        for separation in SEPARATIONS:
            for hold in HOLDS:
                signals[f"soup_{lookback}_{separation}_{hold}"] = signals_for(
                    bars, levels[lookback], separation, hold)
    observed_months = {bar["ts"][:7] for bar in bars if bar["ts"] >= PROTOCOL["start"]}
    rows, month_rows = [], []
    gate = [True] * len(bars)
    for variant in VARIANTS:
        entries, exits = signals[variant]
        curve, trades = [], []
        result = simulate(bars, entries, gate, gate, 0.0, PROTOCOL["start"],
                          fee_bps=PROTOCOL["simulator_cost_bps_per_side"],
                          equity_curve=curve, trade_log=trades, exit_signals=exits)
        months = [item for item in continuous_monthly_windows(
            bars, curve, trades, 2024, PROTOCOL["split"])["all"]
            if item["start"][:7] in observed_months]
        if not months:
            raise ValueError("no_complete_month_with_candles")
        month_rows.extend({"symbol": symbol, "timeframe": timeframe,
                           "variant": variant, **item} for item in months)
        rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                     "bars": len(bars), "pnl_rub": result["pnl_rub"],
                     "net_return_pct": result["return_pct"],
                     "closed_trades": result["closed_trades"],
                     "winning_trades": result["winning_trades"],
                     "profit_factor": result["profit_factor"],
                     "max_drawdown_pct": result["max_drawdown_pct"],
                     "positive_months": sum(item["pnl_rub"] > 0 for item in months),
                     "negative_months": sum(item["pnl_rub"] < 0 for item in months),
                     "zero_months": sum(item["pnl_rub"] == 0 for item in months),
                     "worst_month_pnl_rub": min(item["pnl_rub"] for item in months)})
    return rows, month_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    output = HERE / ("smoke" if args.smoke else "results")
    output.mkdir(exist_ok=True)
    universe = json.loads((CACHE / "universe_2026-10-30.json").read_text(encoding="utf-8"))
    symbols = sorted(item["SECID"] for item in universe if item["BOARDID"] == "TQBR"
                     and source_path(CACHE, item["SECID"], "1D").exists()
                     and source_path(CACHE, item["SECID"], "1H").exists())
    if args.smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    (output / "manifest.json").write_text(json.dumps({
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot": PROTOCOL["source_snapshot"],
        "symbols_attempted": len(symbols), "variants": VARIANTS,
        "timeframes": PROTOCOL["signal_timeframes"],
        "cost_status": PROTOCOL["cost_status"]}, ensure_ascii=False, indent=2))
    all_rows, all_months, skipped, errors, progress = [], [], [], [], []
    for number, symbol in enumerate(symbols, 1):
        for timeframe in PROTOCOL["signal_timeframes"]:
            if not source_path(CACHE, symbol, timeframe).exists():
                skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": "source_missing"})
                continue
            try:
                bars = load_research_bars(CACHE, symbol, timeframe)
                if len(bars) < max(LOOKBACKS) + max(HOLDS) + 34:
                    skipped.append({"symbol": symbol, "timeframe": timeframe,
                                    "reason": "too_few_candles"})
                    continue
                if not any(bar["ts"][:10] >= PROTOCOL["start"] for bar in bars[33:]):
                    skipped.append({"symbol": symbol, "timeframe": timeframe,
                                    "reason": "no_bar_after_start"})
                    continue
                rows, months = evaluate(symbol, timeframe, bars)
                all_rows.extend(rows)
                all_months.extend(months)
            except Exception as exc:
                skipped.append({"symbol": symbol, "timeframe": timeframe, "reason": repr(exc)})
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": repr(exc)})
        progress.append({"symbol": symbol, "status": "ok" if not any(
            item["symbol"] == symbol for item in errors) else "error"})
        if number % 10 == 0 or number == len(symbols):
            write_csv(output / "progress.csv", progress)
            print(f"{number}/{len(symbols)} symbols; {len(all_rows)} pairs; {len(errors)} errors", flush=True)
    write_csv(output / "all_variants.csv", all_rows, ROW_FIELDS)
    write_csv(output / "monthly_returns.csv", all_months)
    write_csv(output / "skipped.csv", skipped, ("symbol", "timeframe", "reason"))
    summary = {"cost_model": PROTOCOL["cost_status"], "errors": errors,
               "skipped": len(skipped), "symbols": len({row["symbol"] for row in all_rows}),
               "rows": len(all_rows), "months": len(all_months)}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    if all_rows:
        build_report(output, PROTOCOL, summary, all_rows, all_months)
        with (output / "REPORT.md").open("a", encoding="utf-8") as report:
            report.write("\n## Происхождение идеи\n\n"
                         "Это тест опубликованного правила Larry Connors о ложном пробое, "
                         "адаптированного под сигналы после закрытия свечи. "
                         "[Авторское описание и точные правила](https://tradingmarkets.com/recent/How_To_Use_TMs_Indicators_The_Turtle_Soup_Plus_One_Lists-665446) "
                         "не содержат полного журнала его личных сделок. "
                         "[Датированные рыночные примеры](https://tradingmarkets.com/recent/how_to_catch_an_explosive_reversal-672426) "
                         "показывают сигналы, а не подтверждённые личные исполнения. "
                         "Доходность этого бэктеста нельзя приписывать трейдеру.\n")
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
