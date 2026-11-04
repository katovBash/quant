"""Run the fixed gross 1D/1W horizontal-level breakout grid on cached MOEX bars."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("htf_level_breakouts", HERE / "levels.py")
LEVELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEVELS)

from src.ema.core.research_ema_combinations import simulate
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.standalone_grid import load_bars


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def year_rows(monthly: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for item in monthly:
        groups[(item["symbol"], item["timeframe"], item["variant"], item["start"][:4])].append(item)
    result = []
    for (symbol, timeframe, variant, year), months in groups.items():
        result.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                       "year": year, "complete": len(months) == 12,
                       "months": len(months), "profitable_months": sum(item["pnl_rub"] > 0 for item in months),
                       "pnl_rub": round(sum(item["pnl_rub"] for item in months), 2),
                       "return_pct": round(100 * (months[-1]["ending_equity_rub"] /
                                                  months[0]["starting_equity_rub"] - 1), 2),
                       "closed_trades": sum(item["closed_trades"] for item in months)})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=HERE / "protocol.json")
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--limit", type=int, help="Smoke test only; no candidate decision")
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    symbols = protocol["symbols"][:args.limit] if args.limit else protocol["symbols"]
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows, monthly, progress, errors = [], [], [], []
    expected_variants = 1 + sum(len(protocol["lookbacks"][source]) for source in protocol["level_timeframes"]) * len(protocol["break_buffers_atr"]) * len(protocol["entry_modes"])
    for symbol in symbols:
        try:
            daily = load_bars(symbol, "1D")
            for timeframe in protocol["signal_timeframes"]:
                bars = load_bars(symbol, timeframe)
                local = LEVELS.local_control(bars)
                variants = [("baseline", "local", 20, 0.0, "immediate", local, local)]
                for source in protocol["level_timeframes"]:
                    for lookback in protocol["lookbacks"][source]:
                        boundaries = LEVELS.levels(bars, daily, source, lookback)
                        for buffer in protocol["break_buffers_atr"]:
                            immediate = LEVELS.breakout_events(
                                bars, boundaries, buffer,
                                min_width_atr=protocol["minimum_channel_width_signal_atr"])
                            for mode in protocol["entry_modes"]:
                                entry = (immediate if mode == "immediate" else
                                         LEVELS.retest_events(bars, boundaries, immediate,
                                                              ttl=protocol["retest_ttl_signal_bars"],
                                                              zone_atr=protocol["retest_zone_atr"]))
                                name = f"{source}_n{lookback}_buffer{buffer:g}_{mode}"
                                variants.append((name, source, lookback, buffer, mode,
                                                 entry, immediate))
                assert len(variants) == expected_variants
                for name, source, lookback, buffer, mode, entry, exit_signal in variants:
                    curve, trades = [], []
                    full = simulate(bars, entry, [True]*len(bars), [True]*len(bars),
                                    0, "2024-01-01", fee_bps=0, equity_curve=curve,
                                    trade_log=trades, exit_signals=exit_signal)
                    windows = continuous_monthly_windows(bars, curve, trades, 2024,
                                                         protocol["split"])
                    items = windows["all"]
                    monthly.extend({"symbol": symbol, "timeframe": timeframe,
                                    "variant": name, **item} for item in items)
                    rows.append({"symbol": symbol, "timeframe": timeframe, "variant": name,
                                 "level_timeframe": source, "lookback": lookback,
                                 "buffer_atr": buffer, "entry_mode": mode,
                                 "closed_trades": full["closed_trades"],
                                 "winning_trades": full["winning_trades"],
                                 "win_rate_pct": round(100 * full["winning_trades"] / full["closed_trades"], 2)
                                                 if full["closed_trades"] else 0,
                                 "pnl_rub": full["pnl_rub"],
                                 "net_return_pct": full["return_pct"],
                                 "profit_factor": full["profit_factor"],
                                 "max_drawdown_pct": full["max_drawdown_pct"],
                                 "months": len(items),
                                 "positive_months": sum(item["pnl_rub"] > 0 for item in items),
                                 "worst_month_pnl_rub": min((item["pnl_rub"] for item in items), default=0),
                                 "late_positive_months": sum(item["pnl_rub"] > 0 and item["sample"] != "train" for item in items)})
                progress.append({"symbol": symbol, "timeframe": timeframe,
                                 "variants": len(variants), "status": "done"})
                print(symbol, timeframe, "done", flush=True)
        except (OSError, ValueError, KeyError, TypeError, AssertionError) as exc:
            errors.append({"symbol": symbol, "error": str(exc)})
            print(symbol, "ERROR", exc, flush=True)
    write_csv(output / "all_variants.csv", rows)
    write_csv(output / "monthly_returns.csv", monthly)
    write_csv(output / "yearly_returns.csv", year_rows(monthly))
    write_csv(output / "progress.csv", progress)
    regimes = []
    groups = defaultdict(list)
    for item in monthly:
        groups[(item["symbol"], item["timeframe"], item["variant"], item["ex_post_regime"])].append(item)
    for (symbol, timeframe, variant, regime), items in groups.items():
        regimes.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                        "ex_post_regime": regime, "months": len(items),
                        "profitable_months": sum(item["pnl_rub"] > 0 for item in items),
                        "pnl_rub": round(sum(item["pnl_rub"] for item in items), 2),
                        "closed_trades": sum(item["closed_trades"] for item in items)})
    write_csv(output / "monthly_regime_profiles.csv", regimes)
    summary = {"protocol": str(args.protocol.resolve()), "cost_model": "gross_before_costs",
               "status": "REVIEW_ONLY", "history_status": "seen_history",
               "symbols": len(symbols), "expected_variants_per_symbol_timeframe": expected_variants,
               "rows": len(rows), "monthly_rows": len(monthly), "errors": errors}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    manifest = {"protocol": str(args.protocol.resolve().relative_to(ROOT)),
                "snapshot": protocol["source_snapshot"], "completed_at": datetime.now().isoformat(),
                "pairs_expected": len(symbols) * len(protocol["signal_timeframes"]) * expected_variants,
                "pairs_observed": len(rows), "errors": len(errors),
                "smoke_test": bool(args.limit)}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if rows:
        build_report(output, protocol, summary, rows, monthly)


if __name__ == "__main__":
    main()
