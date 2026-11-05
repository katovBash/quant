"""Re-simulate saved indicator grids into genuine monthly equity results.

This is an ex-post reconstruction of old experiments, never a preregistered
holdout. Checkpoints make a long full-universe run resumable.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research import indicator_library, standalone_grid
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import sample_period

EXPERIMENTS = ROOT / "experiments"
CACHE = ROOT / "data/candles/moex_scan"
SUPPORTED = {
    "rsi-grid-search": "standalone", "sma-grid-search": "library",
    "macd-grid-search": "library", "roc-grid-search": "library",
}
ROW_FIELDS = ("symbol", "timeframe", "variant", "bars", "pnl_rub", "net_return_pct",
              "closed_trades", "winning_trades", "profit_factor", "max_drawdown_pct")
MONTH_FIELDS = ("symbol", "timeframe", "variant", "start", "end_exclusive", "sample",
                "starting_equity_rub", "ending_equity_rub", "return_pct", "pnl_rub",
                "closed_trades", "winning_trades", "win_rate_pct", "max_drawdown_pct",
                "market_return_pct", "market_range_pct", "ex_post_regime")


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def indicator_name(folder: Path) -> str:
    return folder.name.removesuffix("-grid-search")


def expected_variants(folder: Path, manifest: dict) -> tuple[list[str], dict[str, dict]]:
    kind = SUPPORTED[folder.name]
    if kind == "library":
        specs = manifest["rules"]
        return ["baseline", *[spec["rule_id"] for spec in specs]], {
            spec["rule_id"]: {"family": spec["family"], **spec["parameters"]} for spec in specs}
    name = indicator_name(folder).replace("-", "_")
    # A one-symbol real series is needed for variant IDs because some patterns
    # compute their signal arrays while enumerating variants.
    bars = standalone_grid.load_bars("SBER", "1D")
    specs = [(variant, params) for variant, params, _ in standalone_grid.variants(name, bars)]
    mapping = {f"{variant}__{mode}": {**params, "mode": mode}
               for variant, params in specs for mode in standalone_grid.MODES}
    return ["baseline", *mapping], mapping


def pair(folder: Path, symbol: str, timeframe: str, tick: float,
         manifest: dict) -> tuple[list[dict], list[dict]]:
    bars = standalone_grid.load_bars(symbol, timeframe)
    if len(bars) < 250:
        raise ValueError(f"insufficient_bars:{len(bars)}")
    start, split = sample_period(timeframe)
    observed_months = {bar["ts"][:7] for bar in bars if bar["ts"][:10] >= start}
    always = [True] * len(bars)
    never = [False] * len(bars)
    entries = [0] * len(bars)
    first = next((i for i in range(33, len(bars)) if bars[i]["ts"][:10] >= start), None)
    if first is None:
        raise ValueError("no_bar_after_start")
    entries[first - 1] = 1
    signals: list[tuple[str, list[int], list[bool], list[bool]]] = [
        ("baseline", entries, always, never)]
    if SUPPORTED[folder.name] == "library":
        signals.extend((spec["rule_id"], indicator_library.signal_series(bars, spec), always, always)
                       for spec in manifest["rules"])
    else:
        name = indicator_name(folder).replace("-", "_")
        for variant, _params, series in standalone_grid.variants(name, bars):
            for mode in standalone_grid.MODES:
                signals.append((f"{variant}__{mode}", series,
                                never if mode == "short" else always,
                                never if mode == "long" else always))
    rows, months = [], []
    for variant, series, up, down in signals:
        curve, trades = [], []
        result = simulate(bars, series, up, down, tick, start,
                          equity_curve=curve, trade_log=trades)
        monthly = [row for row in continuous_monthly_windows(
            bars, curve, trades, int(start[:4]), split)["all"]
            if row["start"][:7] in observed_months]
        if not monthly:
            raise ValueError("no_complete_month")
        rows.append({"symbol": symbol, "timeframe": timeframe, "variant": variant,
                     "bars": len(bars), "pnl_rub": result["pnl_rub"],
                     "net_return_pct": result["return_pct"],
                     "closed_trades": result["closed_trades"],
                     "winning_trades": result["winning_trades"],
                     "profit_factor": result["profit_factor"],
                     "max_drawdown_pct": result["max_drawdown_pct"]})
        months.extend({"symbol": symbol, "timeframe": timeframe,
                       "variant": variant, **month} for month in monthly)
    return rows, months


def rebuild(folder: Path, *, limit: int = 0) -> dict:
    folder = folder.resolve()
    if folder.name not in SUPPORTED:
        raise ValueError("unsupported old grid; no exact monthly replay: " + folder.name)
    results = folder / "results"
    manifest = json.loads((results / "manifest.json").read_text(encoding="utf-8"))
    inventory = {item["SECID"]: item for item in json.loads(
        (ROOT / manifest["universe"]).read_text(encoding="utf-8"))}
    symbols = manifest["symbols"][:limit] if limit else manifest["symbols"]
    frames = manifest["timeframes"]
    work = results / ".monthly_work"
    work.mkdir(exist_ok=True)
    skipped = []
    for symbol in symbols:
        for frame in frames:
            stem = work / frame / symbol
            rows_file, months_file = stem.with_suffix(".rows.csv"), stem.with_suffix(".months.csv")
            if rows_file.is_file() and months_file.is_file():
                continue
            try:
                rows, months = pair(folder, symbol, frame, float(inventory[symbol].get("MINSTEP") or 0), manifest)
                write_csv(rows_file, ROW_FIELDS, rows)
                write_csv(months_file, MONTH_FIELDS, months)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                skipped.append({"symbol": symbol, "timeframe": frame, "reason": str(exc)})
        print(folder.name, symbol, "finished", flush=True)
    if limit:
        return {"status": "SMOKE", "symbols": len(symbols), "skipped": len(skipped)}
    all_rows, all_months = [], []
    for symbol in symbols:
        for frame in frames:
            stem = work / frame / symbol
            rows_file, months_file = stem.with_suffix(".rows.csv"), stem.with_suffix(".months.csv")
            if rows_file.is_file() and months_file.is_file():
                all_rows.extend(read_csv(rows_file))
                all_months.extend(read_csv(months_file))
            elif not any(x["symbol"] == symbol and x["timeframe"] == frame for x in skipped):
                skipped.append({"symbol": symbol, "timeframe": frame,
                                "reason": "missing_replay_checkpoint"})
    write_csv(results / "all_variants.csv", ROW_FIELDS, all_rows)
    write_csv(results / "monthly_returns.csv", MONTH_FIELDS, all_months)
    write_csv(results / "skipped.csv", ("symbol", "timeframe", "reason"), skipped)
    summary = {"cost_model": "historical_cost_model_incomplete", "errors": [],
               "symbols": len({row["symbol"] for row in all_rows}),
               "rows": len(all_rows), "months": len(all_months),
               "reconstructed_from": "original frozen candles and signal implementation",
               "reconstructed_on": datetime.now(timezone.utc).isoformat()}
    (results / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    protocol_file = folder / "protocol.json"
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    variants, mapping = expected_variants(folder, manifest)
    protocol.update({
        "signal_timeframes": frames,
        "eligible_universe": {"snapshot_file": manifest["universe"],
                              "cache_dir": "data/candles/moex_scan",
                              "symbols": manifest["symbols"],
                              "requires_source_timeframes": ["1D", "1H"]},
        "parameter_grid": {"axes": {"variant": {"values": variants[1:]}},
                           "variant_template": "{variant}", "include_baseline": True,
                           "max_combinations": len(variants)},
        "expected_variants": variants,
        "legacy_variant_parameters": mapping,
        "baseline": "25% buy-and-hold from first eligible bar on same candles",
        "primary_evaluation": "monthly",
        "signal_rule": "Exact signals from src/research/standalone_grid.py or indicator_library.py; confirmed candle, next-open fill",
        "initial_capital_rub": 1_000_000,
        "position_weight_pct": 25,
        "cost_status": "historical_cost_model_incomplete",
        "split": "2025-01-01",
        "late_sample_status": "seen_history",
        "run_command": "python3 scripts/rebuild_legacy_months.py --experiment " +
                       str(folder.relative_to(ROOT)),
        "reconstruction_status": "ex_post_from_old_frozen_signal_code"})
    protocol_file.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
    return {"status": "RECONSTRUCTED", "symbols": summary["symbols"],
            "rows": len(all_rows), "months": len(all_months), "skipped": len(skipped)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="smoke first N symbols only")
    args = parser.parse_args()
    print(json.dumps(rebuild(args.experiment, limit=args.limit), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
