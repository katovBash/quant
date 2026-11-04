"""Summarize the forecast-only experiment from its saved CSVs."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
FRAMES = ("15M", "30M", "1H", "4H", "1D")
LABELS = ("range", "trend_up", "trend_down")


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize(results: Path = RESULTS, *, lookback: int = 20, width: float = 6,
              displacement: float = 2, horizon: int = 5, min_observations: int = 30) -> dict:
    selected = []
    for timeframe in FRAMES:
        for path in sorted((results / timeframe).glob("*/forecast.csv")):
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    if (int(row["lookback"]) == lookback and float(row["max_width_atr"]) == width
                            and float(row["min_displacement_atr"]) == displacement
                            and int(row["horizon"]) == horizon and row["sample"] == "holdout"
                            and row["label"] in LABELS):
                        selected.append({"symbol": row["symbol"], "timeframe": timeframe,
                                         "label": row["label"], "observations": int(row["observations"]),
                                         "hit_rate_pct": row["hit_rate_pct"],
                                         "baseline_hit_rate_pct": row["baseline_hit_rate_pct"],
                                         "lift_pp": row["lift_pp"]})
    grouped = defaultdict(list)
    for row in selected:
        grouped[(row["timeframe"], row["label"])].append(row)
    overview = []
    top = []
    for timeframe in FRAMES:
        for label in LABELS:
            rows = grouped[(timeframe, label)]
            eligible = [row for row in rows if row["observations"] >= min_observations and row["lift_pp"] != ""]
            lifts = [float(row["lift_pp"]) for row in eligible]
            overview.append({"timeframe": timeframe, "label": label,
                             "tickers_with_results": len(rows), "tickers_min_observations": len(eligible),
                             "min_observations": min_observations,
                             "positive_lift_tickers": sum(value > 0 for value in lifts),
                             "median_lift_pp": round(statistics.median(lifts), 2) if lifts else "",
                             "median_hit_rate_pct": round(statistics.median(float(row["hit_rate_pct"]) for row in eligible), 2)
                             if eligible else ""})
            top.extend(sorted(eligible, key=lambda row: float(row["lift_pp"]), reverse=True)[:5])
    results.mkdir(parents=True, exist_ok=True)
    fields = ("symbol", "timeframe", "label", "observations", "hit_rate_pct",
              "baseline_hit_rate_pct", "lift_pp")
    write_csv(results / "selected_forecasts.csv", selected, fields)
    write_csv(results / "forecast_overview.csv", overview,
              ("timeframe", "label", "tickers_with_results", "tickers_min_observations",
               "min_observations", "positive_lift_tickers", "median_lift_pp", "median_hit_rate_pct"))
    write_csv(results / "top5_forecasts.csv", top, fields)
    return {"selected_rows": len(selected), "overview_rows": len(overview), "top_rows": len(top)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS)
    args = parser.parse_args()
    print(summarize(args.results))


if __name__ == "__main__":
    main()
