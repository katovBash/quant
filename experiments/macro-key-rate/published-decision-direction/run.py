"""Full-universe test of trading after published key-rate decisions."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.experiment_report import build_report
from src.research.key_rate_event import decision_outcome_rows, decision_signals
from src.research.parameter_grid import variants_from_grid
from src.research.timeframes import load_research_bars, source_path
from src.research.trader_method_run import run, write_csv

HERE = Path(__file__).resolve().parent


def main(smoke: bool = False) -> None:
    protocol = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
    events = json.loads((HERE / "decisions.json").read_text(encoding="utf-8"))["events"]
    decisions = {item["date"]: item for item in events}
    if len(decisions) != 23 or variants_from_grid(protocol["parameter_grid"]) != protocol["expected_variants"]:
        raise ValueError("frozen event dates or parameter grid changed")
    if any(events[i]["announced_rate"] != events[i + 1]["previous_rate"]
           for i in range(len(events) - 1)):
        raise ValueError("published rate sequence is inconsistent")

    def factory(variant: str, bars: list[dict]):
        mapping, hold = variant.rsplit("_", 1)
        return decision_signals(bars, decisions, mapping, int(hold))

    run_result = run(HERE, smoke=smoke, signal_factory=factory)
    output = HERE / ("smoke" if smoke else "results")
    universe = json.loads((ROOT / protocol["eligible_universe"]["snapshot_file"]).read_text())
    symbols = sorted({item["SECID"] for item in universe if item["BOARDID"] == "TQBR"})
    if smoke:
        symbols = [symbol for symbol in ("SBER", "GAZP") if symbol in symbols]
    outcome_rows = []
    for symbol in symbols:
        if not source_path(ROOT / "data/candles/moex_scan", symbol, "1H").exists():
            continue
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, "1H")
        for mapping in ("conventional", "inverse", "hold_long", "hold_short"):
            for hold in (1, 3, 6):
                outcome_rows.extend(decision_outcome_rows(symbol, bars, decisions, mapping, hold))
    write_csv(output / "decision_outcomes.csv", outcome_rows)
    grouped = defaultdict(list)
    for row in outcome_rows:
        grouped[(row["event_date"], row["mapping"], row["hold_bars"])].append(
            float(row["approx_account_return_pct"]))
    date_rows = []
    for (date_key, mapping, hold), values in sorted(grouped.items()):
        date_rows.append({"event_date": date_key, "mapping": mapping,
                          "hold_bars": hold, "symbols": len(values),
                          "median_approx_account_return_pct": round(statistics.median(values), 6),
                          "mean_approx_account_return_pct": round(statistics.mean(values), 6),
                          "profitable_stocks": sum(value > 0 for value in values)})
    write_csv(output / "decision_date_summary.csv", date_rows,
              ("event_date", "mapping", "hold_bars", "symbols",
               "median_approx_account_return_pct", "mean_approx_account_return_pct",
               "profitable_stocks"))
    by_variant = defaultdict(list)
    for row in date_rows:
        by_variant[f"{row['mapping']}_{row['hold_bars']}"].append(
            float(row["median_approx_account_return_pct"]))
    variant_dates = {name: {"dates": len(values),
                            "positive_date_medians": sum(value > 0 for value in values),
                            "median_of_date_medians_pct": round(statistics.median(values), 6)}
                     for name, values in sorted(by_variant.items())}
    counts = {"hike": sum(x["announced_rate"] > x["previous_rate"] for x in events),
              "cut": sum(x["announced_rate"] < x["previous_rate"] for x in events),
              "hold": sum(x["announced_rate"] == x["previous_rate"] for x in events)}
    evidence = {"scheduled_decision_dates": len(events), "rate_decision_counts": counts,
                "stock_event_variant_rows": len(outcome_rows), "variant_dates": variant_dates,
                "timestamp_caveat": "13:30 appears in the official decision archive and many press release metadata; delivery to trader terminal is not measured; entry is delayed until 15:00",
                "outcome_caveat": "per-date diagnostic uses approximate 25% account exposure and 30bp round-trip costs; precise cash PnL is in monthly_returns.csv"}
    (output / "decision_event_summary.json").write_text(json.dumps(
        evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (output / "all_variants.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with (output / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        months = list(csv.DictReader(stream))
    build_report(output, protocol, run_result, rows, months)
    print(json.dumps({"rows": run_result["rows"], **evidence}, ensure_ascii=False))


if __name__ == "__main__":
    main(smoke="--smoke" in sys.argv)
