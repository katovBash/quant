"""EMA25 as intraday zone plus projected confirmed daily/weekly pivot lines."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.ema_zone_lines import (higher_lines, higher_range_zones,
                                         line_ema_gates, line_retest_signals)
from src.research.experiment_report import build_report
from src.research.monthly_efficiency import (calendar_year_windows,
                                             continuous_monthly_windows, monthly_windows)
from src.research.standalone_grid import UNIVERSE, ema_level_signals, load_bars
from src.research.trade_windows import trade_windows

HERE = Path(__file__).resolve().parent
PROTOCOL = HERE / "protocol.json"
OUT = HERE / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    output = args.out.resolve()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    monthly_mode = protocol.get("primary_evaluation") == "monthly"
    fee_bps = float(protocol.get("fee_bps_per_side", 5))
    ticks = {item["SECID"]: float(item.get("MINSTEP") or 0)
             for item in json.loads(UNIVERSE.read_text(encoding="utf-8"))}
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    annual_regimes = []
    month_rows = []
    month_regime_rows = []
    year_rows = []
    rolling_trade_rows = []
    trade_block_rows = []
    monthly = {"protocol": str(protocol_path.relative_to(ROOT)),
               "snapshot": "2026-10-30", "history_status": "seen_history",
               "pairs": [], "errors": []}
    for symbol in protocol["symbols"]:
        try:
            tick = ticks[symbol] if protocol.get("slippage") != "none" else 0.0
            daily = load_bars(symbol, "1D")
            hourly = load_bars(symbol, "1H") if "4H" in protocol["higher_line_timeframes"] else None
            for timeframe in protocol["signal_timeframes"]:
                bars = load_bars(symbol, timeframe)
                signals = ema_level_signals(bars, 25, 0.5)
                always = [True] * len(bars)
                base_log = []
                base_curve = [] if monthly_mode else None
                base = simulate(bars, signals, always, always, tick, "2024-01-01",
                                trade_log=base_log, equity_curve=base_curve,
                                fee_bps=fee_bps)
                base_monthly = (continuous_monthly_windows(bars, base_curve, base_log, 2024,
                                                           protocol["split"])
                                if monthly_mode else monthly_windows(
                                    bars, signals, always, tick, 2024, protocol["split"],
                                    fee_bps=fee_bps))
                variants = [{"name": "baseline", "source": "", "wing": "",
                             "range_window": "", "min_touches": "",
                             "distance": "", "bend": "", "ema_mode": "",
                             "up": always, "down": always,
                             "entry_signals": signals, "exit_signals": None}]
                for source in protocol["higher_line_timeframes"]:
                    definitions = []
                    if protocol.get("higher_level_model") == "outer_range":
                        for window in protocol["higher_range_windows"][source]:
                            for touches in protocol["higher_range_min_touches"]:
                                definitions.append((f"_range_{window}_touch_{touches}", "",
                                                    window, touches,
                                                    higher_range_zones(bars, daily, source,
                                                                       window, touches)))
                    else:
                        for wing in protocol.get("higher_line_pivot_wings", [None]):
                            definitions.append((f"_wing_{wing}" if wing is not None else "",
                                                wing, "", "",
                                                higher_lines(bars, daily, source,
                                                             hourly=hourly, wing=wing,
                                                             max_age=protocol.get(
                                                                 "higher_line_max_pivot_age"))))
                    for label, wing, range_window, touches, lines in definitions:
                        for distance in protocol["higher_line_zone_atr"]:
                            if protocol.get("signal_family") == "line_retest":
                                for ema_mode in protocol["ema_retest_modes"]:
                                    entry = line_retest_signals(
                                        bars, lines, distance, ema_mode,
                                        min_channel_atr=protocol.get("min_channel_signal_atr", 0))
                                    variants.append({"name": f"{source}{label}_zone_{distance:g}_retest_{ema_mode}",
                                                     "source": source, "wing": wing,
                                                     "range_window": range_window,
                                                     "min_touches": touches,
                                                     "distance": distance, "bend": 1,
                                                     "ema_mode": ema_mode, "up": always,
                                                     "down": always, "entry_signals": entry,
                                                     "exit_signals": signals})
                            else:
                                for bend in protocol["bend_bars"]:
                                    up, down = line_ema_gates(bars, lines, distance, bend)
                                    variants.append({"name": f"{source}{label}_zone_{distance:g}_bend_{bend}",
                                                     "source": source, "wing": wing,
                                                     "range_window": range_window,
                                                     "min_touches": touches,
                                                     "distance": distance, "bend": bend,
                                                     "ema_mode": "turn", "up": up,
                                                     "down": down, "entry_signals": signals,
                                                     "exit_signals": None})
                for variant in variants:
                    name, source, wing, distance, bend = (variant[key] for key in
                                                          ("name", "source", "wing", "distance", "bend"))
                    up, down = variant["up"], variant["down"]
                    entry_signals, exit_signals = variant["entry_signals"], variant["exit_signals"]
                    log = [] if name != "baseline" else base_log
                    curve = ([] if monthly_mode else None) if name != "baseline" else base_curve
                    full = base if name == "baseline" else simulate(
                        bars, entry_signals, up, down, tick, "2024-01-01",
                        trade_log=log, equity_curve=curve, exit_signals=exit_signals,
                        fee_bps=fee_bps)
                    rolling = trade_windows(log) if not monthly_mode else []
                    blocks = trade_windows(log, step=100) if not monthly_mode else []
                    rolling_trade_rows.extend({"symbol": symbol, "timeframe": timeframe,
                                               "variant": name, **item} for item in rolling)
                    trade_block_rows.extend({"symbol": symbol, "timeframe": timeframe,
                                             "variant": name, **item} for item in blocks)
                    windows = (base_monthly if name == "baseline" else
                               continuous_monthly_windows(bars, curve, log, 2024, protocol["split"])
                               if monthly_mode else monthly_windows(
                                   bars, entry_signals, up, tick, 2024, protocol["split"],
                                   down, exit_signals, fee_bps))
                    years = calendar_year_windows(bars, entry_signals, up, tick,
                                                  2024, down, exit_signals, fee_bps)
                    month_rows.extend({"symbol": symbol, "timeframe": timeframe,
                                       "variant": name, **item} for item in windows["all"])
                    for regime in ("growth", "decline", "sideways", "volatile_mixed", "no_data"):
                        regime_months = [item for item in windows["all"]
                                         if item["ex_post_regime"] == regime]
                        if regime_months:
                            month_regime_rows.append({
                                "symbol": symbol, "timeframe": timeframe, "variant": name,
                                "regime": regime, "months": len(regime_months),
                                "positive_months": sum(item["pnl_rub"] > 0 for item in regime_months),
                                "total_pnl_rub": round(sum(item["pnl_rub"] for item in regime_months), 2),
                                "median_pnl_rub": round(statistics.median(
                                    item["pnl_rub"] for item in regime_months), 2),
                                "closed_trades": sum(item["closed_trades"] for item in regime_months)})
                    year_rows.extend({"symbol": symbol, "timeframe": timeframe,
                                      "variant": name, **item} for item in years)
                    complete_years = [item for item in years if not item["partial"]]
                    for item in complete_years:
                        annual_regimes.append({"timeframe": timeframe,
                                               "source": source or "baseline",
                                               "regime": item["ex_post_regime"],
                                               "return_pct": item["return_pct"]})
                    early = [item for item in windows["all"] if item["sample"] == "train"]
                    late = [item for item in windows["all"] if item["sample"] != "train"]
                    losing_streak = max_losing_streak = 0
                    for item in windows["all"]:
                        losing_streak = losing_streak + 1 if item["pnl_rub"] <= 0 else 0
                        max_losing_streak = max(max_losing_streak, losing_streak)
                    row = {"symbol": symbol, "timeframe": timeframe, "variant": name,
                           "higher_timeframe": source, "pivot_wing": wing,
                           "range_window": variant["range_window"],
                           "min_touches": variant["min_touches"],
                           "zone_atr": distance, "ema_mode": variant["ema_mode"],
                           "bend_bars": bend, "closed_trades": full["closed_trades"],
                           "winning_trades": full["winning_trades"],
                           "win_rate_pct": round(100 * full["winning_trades"] / full["closed_trades"], 2)
                                           if full["closed_trades"] else None,
                           "net_return_pct": full["return_pct"],
                           "pnl_rub": full["pnl_rub"],
                           "profit_factor": full["profit_factor"],
                           "max_drawdown_pct": full["max_drawdown_pct"],
                           "rolling_100_windows": len(rolling) if not monthly_mode else None,
                           "profitable_rolling_100_windows": sum(item["pnl_rub"] > 0 for item in rolling),
                           "worst_100_trade_pnl_rub": min((item["pnl_rub"] for item in rolling), default=None),
                           "median_100_trade_pnl_rub": round(statistics.median(
                               item["pnl_rub"] for item in rolling), 2) if rolling else None,
                           "months": windows["count"],
                           "positive_months": windows["count"] - windows["nonpositive_count"],
                           "positive_month_share_pct": round(100 * (windows["count"] - windows["nonpositive_count"])
                                                              / windows["count"], 2) if windows["count"] else None,
                           "months_with_trades": windows["count"] - windows["zero_trade_count"],
                           "max_consecutive_nonpositive_months": max_losing_streak,
                           "nonpositive_months": windows["nonpositive_count"],
                           "zero_trade_months": windows["zero_trade_count"],
                           "worst_month_pct": windows["worst"]["return_pct"],
                           "worst_month_pnl_rub": windows["worst"]["pnl_rub"],
                           "median_month_pct": windows["median_return_pct"],
                           "median_month_pnl_rub": round(statistics.median(
                               item["pnl_rub"] for item in windows["all"]), 2),
                           "early_nonpositive_months": sum(item["return_pct"] <= 0 for item in early),
                           "late_nonpositive_months": sum(item["return_pct"] <= 0 for item in late),
                           "complete_years": len(complete_years),
                           "nonpositive_years": sum(item["return_pct"] <= 0 for item in complete_years),
                           "year_regimes_seen": ",".join(sorted({item["ex_post_regime"] for item in complete_years})),
                           "delta_return_pp": round(full["return_pct"]-base["return_pct"], 2),
                           "delta_nonpositive_months": windows["nonpositive_count"]-base_monthly["nonpositive_count"],
                           "delta_closed_trades": full["closed_trades"]-base["closed_trades"]}
                    rows.append(row)
                    monthly["pairs"].append({"symbol": symbol, "timeframe": timeframe,
                                             "variant": name,
                                             "continuous_months": windows if monthly_mode else None,
                                             "monthly_start_windows": None if monthly_mode else {"1": windows},
                                             "calendar_years": years})
                print(symbol, timeframe, "done", flush=True)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            monthly["errors"].append({"symbol": symbol, "error": str(exc)})
            print(symbol, "ERROR", exc, flush=True)
    with (output / "all_variants.csv").open("w", newline="", encoding="utf-8") as stream:
        if rows:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    reports = [("monthly_returns.csv", month_rows),
               ("monthly_regime_profiles.csv", month_regime_rows),
               ("yearly_returns.csv", year_rows)]
    if monthly_mode:
        for filename in ("trade_windows_100.csv", "trade_blocks_100.csv"):
            (output / filename).unlink(missing_ok=True)
    else:
        reports.extend((("trade_windows_100.csv", rolling_trade_rows),
                        ("trade_blocks_100.csv", trade_block_rows)))
    for filename, values in reports:
        with (output / filename).open("w", newline="", encoding="utf-8") as stream:
            if values:
                writer = csv.DictWriter(stream, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
    (output / "monthly_validation.json").write_text(
        json.dumps(monthly, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    by_group = {}
    for timeframe in protocol["signal_timeframes"]:
        for source in ("baseline", *protocol["higher_line_timeframes"]):
            subset = [row for row in rows if row["timeframe"] == timeframe
                      and (row["variant"] == "baseline" if source == "baseline"
                           else row["higher_timeframe"] == source)]
            if not subset:
                continue
            by_group[f"{timeframe}_{source}"] = {
                "rows": len(subset),
                "all_positive_months": sum(row["months"] >= 1 and row["nonpositive_months"] == 0
                                           for row in subset),
                "annual_strict_pass": sum(row["complete_years"] >= 2 and row["nonpositive_years"] == 0
                                          for row in subset),
                "fewer_trades": sum(row["delta_closed_trades"] < 0 for row in subset),
                "fewer_nonpositive_months": sum(row["delta_nonpositive_months"] < 0 for row in subset),
                "higher_full_return": sum(row["delta_return_pp"] > 0 for row in subset),
                "median_return_change_pp": round(statistics.median(row["delta_return_pp"] for row in subset), 2),
                "median_trade_change": round(statistics.median(row["delta_closed_trades"] for row in subset), 1),
                "median_positive_month_share_pct": round(statistics.median(
                    row["positive_month_share_pct"] for row in subset), 2),
                "best_positive_month_share_pct": max(row["positive_month_share_pct"] for row in subset),
                "median_worst_month_pnl_rub": round(statistics.median(
                    row["worst_month_pnl_rub"] for row in subset), 2),
                "complete_year_regimes": {
                    regime: {"observations": len(values),
                             "positive": sum(value > 0 for value in values),
                             "median_return_pct": round(statistics.median(values), 2) if values else None}
                    for regime in ("growth", "decline", "sideways", "volatile_mixed")
                    for values in [[item["return_pct"] for item in annual_regimes
                                    if item["timeframe"] == timeframe and item["source"] == source
                                    and item["regime"] == regime]]},
            }
    trade_eligible = [row for row in rows if row["variant"] != "baseline"
                      and row["closed_trades"] >= 100]
    passing = [row for row in trade_eligible
               if row["net_return_pct"] > 0 and float(row["profit_factor"]) > 1.2
               and abs(row["max_drawdown_pct"]) <= 20
               and row["delta_closed_trades"] < 0]
    summary = {"rows": len(rows), "monthly_rows": len(month_rows),
               "cost_model": "gross_before_costs" if fee_bps == 0 and protocol.get("slippage") == "none"
                             else "commission_and_one_tick_only",
               "yearly_rows": len(year_rows),
               "rolling_100_trade_windows": len(rolling_trade_rows),
               "nonoverlapping_100_trade_blocks": len(trade_block_rows),
               "filtered_100_trade_pass": None if monthly_mode else len(trade_eligible),
               "filtered_preliminary_pass": None if monthly_mode else len(passing),
               "decision": ("REVIEW_ONLY" if monthly_mode else
                            "NO_CANDIDATE" if not passing else "REVIEW_ONLY"),
               "by_group": by_group, "errors": monthly["errors"]}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    build_report(output, protocol, summary, rows, month_rows)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
