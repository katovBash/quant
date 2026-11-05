"""Run preregistered full-universe rate-decision event study and trading rules."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.key_rate_event import event_signals, matched_event_rows
from src.research.experiment_report import build_report
from src.research.timeframes import load_research_bars, source_path
from src.research.trader_method_run import run, write_csv
from src.research.parameter_grid import variants_from_grid

HERE = Path(__file__).resolve().parent


def main(smoke: bool = False) -> None:
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    dates = set(json.loads((HERE / "events.json").read_text(encoding="utf-8"))["dates"])
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]

    def factory(variant: str, bars: list[dict]):
        direction, hold = variant.rsplit("_", 1)
        return event_signals(bars, dates, direction, int(hold))

    result = run(HERE, smoke=smoke, signal_factory=factory)
    output = HERE / ("smoke" if smoke else "results")
    universe = json.loads((ROOT / protocol["eligible_universe"]["snapshot_file"]).read_text())
    symbols = sorted({item["SECID"] for item in universe if item["BOARDID"] == "TQBR"})
    if smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    event_rows, missing = [], []
    for symbol in symbols:
        if not source_path(ROOT / "data/candles/moex_scan", symbol, "1H").exists():
            continue
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, "1H")
        rows, skipped = matched_event_rows(symbol, bars, dates)
        event_rows.extend(rows)
        missing.extend(skipped)
    write_csv(output / "event_study.csv", event_rows)
    write_csv(output / "event_study_missing.csv", missing,
              ("symbol", "event_date", "reason"))
    grouped = defaultdict(list)
    for row in event_rows:
        grouped[row["event_date"]].append(row)
    per_date = []
    for event_date, rows in sorted(grouped.items()):
        differences = [float(row["abs_return_difference_pp"]) for row in rows]
        ratios = [float(row["volume_ratio"]) for row in rows if row["volume_ratio"] != ""]
        per_date.append({"event_date": event_date, "symbols": len(rows),
                         "median_abs_return_difference_pp": round(statistics.median(differences), 6),
                         "mean_abs_return_difference_pp": round(statistics.mean(differences), 6),
                         "median_volume_ratio": round(statistics.median(ratios), 6) if ratios else "",
                         "stocks_with_larger_abs_move": sum(x > 0 for x in differences)})
    write_csv(output / "event_date_summary.csv", per_date,
              ("event_date", "symbols", "median_abs_return_difference_pp",
               "mean_abs_return_difference_pp", "median_volume_ratio",
               "stocks_with_larger_abs_move"))
    observation = {"scheduled_events": len(dates), "matched_events": len(per_date),
                   "matched_stock_event_pairs": len(event_rows), "missing_stock_event_pairs": len(missing),
                   "dates_with_larger_median_abs_move": sum(
                       row["median_abs_return_difference_pp"] > 0 for row in per_date),
                   "median_of_event_date_median_abs_difference_pp":
                       round(statistics.median(row["median_abs_return_difference_pp"] for row in per_date), 6)
                       if per_date else None,
                   "median_of_event_date_median_volume_ratio":
                       round(statistics.median(row["median_volume_ratio"] for row in per_date
                                               if row["median_volume_ratio"] != ""), 6)
                       if any(row["median_volume_ratio"] != "" for row in per_date) else None,
                   "conclusion_scope": "matched hourly event study, not causal attribution or a verified release-surprise strategy"}
    (output / "event_study_summary.json").write_text(json.dumps(
        observation, ensure_ascii=False, indent=2) + "\n")
    with (output / "all_variants.csv").open(newline="", encoding="utf-8") as stream:
        all_rows = list(csv.DictReader(stream))
    with (output / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        monthly_rows = list(csv.DictReader(stream))
    build_report(output, protocol, result, all_rows, monthly_rows)
    print(json.dumps({"trading_rows": result["rows"], **observation}, ensure_ascii=False))


if __name__ == "__main__":
    main(smoke="--smoke" in sys.argv)
