"""Re-simulate long and short separately for the ten displayed legacy cases."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.rebuild_legacy_months import SUPPORTED
from src.ema.core.research_ema_combinations import simulate
from src.research import indicator_library, standalone_grid
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.experiment_report import _side_analysis
from src.research.timeframes import sample_period

FIELDS = ("symbol", "timeframe", "variant", "mode", "long_closed", "long_wins",
          "short_closed", "short_wins", "return_pct", "profitable_months", "months",
          "conclusion")


def top_cases(folder: Path) -> list[dict]:
    path = folder / "results/monthly_case_summary.csv"
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = [row for row in csv.DictReader(stream) if row["variant"] != "baseline"
                and int(row["months"]) > 0]
    return sorted(rows, key=lambda row: (int(row["profitable_months"]),
                                         float(row["worst_month_pnl_rub"]),
                                         float(row["full_period_pnl_rub"])),
                  reverse=True)[:10]


def signals_for(folder: Path, bars: list[dict], variant: str, manifest: dict) -> list[int]:
    if SUPPORTED[folder.name] == "library":
        spec = next(item for item in manifest["rules"] if item["rule_id"] == variant)
        return indicator_library.signal_series(bars, spec)
    base = variant.rsplit("__", 1)[0]
    family = folder.name.removesuffix("-grid-search").replace("-", "_")
    return next(series for name, _params, series in standalone_grid.variants(family, bars)
                if name == base)


def examine(folder: Path) -> int:
    manifest = json.loads((folder / "results/manifest.json").read_text())
    inventory = {item["SECID"]: item for item in json.loads(
        (ROOT / manifest["universe"]).read_text())}
    output = []
    for case in top_cases(folder):
        symbol, frame, variant = case["symbol"], case["timeframe"], case["variant"]
        bars = standalone_grid.load_bars(symbol, frame)
        signals = signals_for(folder, bars, variant, manifest)
        tick = float(inventory[symbol].get("MINSTEP") or 0)
        start, split = sample_period(frame)
        always, never = [True] * len(bars), [False] * len(bars)
        parts = []
        for mode, up, down in (("long_only", always, never),
                               ("short_only", never, always),
                               ("long_short", always, always)):
            curve: list[dict] = []
            trades: list[dict] = []
            result = simulate(bars, signals, up, down, tick, start,
                              equity_curve=curve, trade_log=trades)
            valid = bool(curve) and all(math.isfinite(item["equity"]) and
                                            item["equity"] > 0 for item in curve)
            if valid:
                observed = {bar["ts"][:7] for bar in bars if bar["ts"][:10] >= start}
                monthly = [item for item in continuous_monthly_windows(
                    bars, curve, trades, int(start[:4]), split)["all"]
                    if item["start"][:7] in observed]
            else:
                monthly = []
            item = {"symbol": symbol, "timeframe": frame, "variant": variant,
                    "mode": mode,
                    "long_closed": sum(item["side"] == "long" for item in trades),
                    "long_wins": sum(item["side"] == "long" and item["pnl_rub"] > 0 for item in trades),
                    "short_closed": sum(item["side"] == "short" for item in trades),
                    "short_wins": sum(item["side"] == "short" and item["pnl_rub"] > 0 for item in trades),
                    "return_pct": result["return_pct"],
                    "profitable_months": sum(item["pnl_rub"] > 0 for item in monthly),
                    "months": len(monthly),
                    "conclusion": "Капитал ≤ 0: вариант недопустим" if not valid else "—"}
            parts.append(item)
        long, short, both = parts
        if long["conclusion"] == "—" and short["conclusion"] == "—":
            eligible = [item for item in (long, short)
                        if item["return_pct"] > 0 and item["months"] >= 6
                        and item["profitable_months"] * 2 > item["months"]
                        and item["long_closed"] + item["short_closed"] >= 10]
            if eligible:
                best = max(eligible, key=lambda item: (item["profitable_months"] / item["months"],
                                                       item["return_pct"]))
                best["conclusion"] = "К следующей проверке: " + best["mode"]
                both["conclusion"] = best["conclusion"]
            else:
                both["conclusion"] = "Нет направления для рекомендации"
        else:
            both["conclusion"] = "Есть недопустимый режим; рекомендация отложена"
        output.extend(parts)
    if not output:
        return 0
    path = folder / "results/trade_side_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    report = folder / "results/REPORT.md"
    if report.is_file():
        marker = "## Long и short по отдельности"
        body = report.read_text(encoding="utf-8").split(marker, 1)[0].rstrip()
        report.write_text(body + "\n\n" + marker + "\n\n" +
                          _side_analysis(folder / "results") + "\n", encoding="utf-8")
    return len(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path)
    args = parser.parse_args()
    folders = [args.experiment] if args.experiment else [ROOT / "experiments" / name for name in SUPPORTED]
    for folder in folders:
        if folder.name in SUPPORTED:
            print(folder.name, examine(folder), flush=True)


if __name__ == "__main__":
    main()
