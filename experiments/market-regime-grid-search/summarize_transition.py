"""Aggregate range-transition frequencies across tickers without pooling bars."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "transition-results"
FRAMES = ("15M", "30M", "1H", "4H", "1D")
OUTCOMES = ("up", "down", "no_break")
FIELDS = ("timeframe", "horizon", "feature", "bucket", "outcome",
          "tickers_with_results", "tickers_min_episodes", "min_episodes",
          "positive_delta_tickers", "median_delta_pp", "median_conditional_pct",
          "median_baseline_pct")


def summarize(results: Path = RESULTS, *, min_episodes: int = 20) -> list[dict]:
    groups = defaultdict(list)
    for timeframe in FRAMES:
        for path in sorted((results / timeframe).glob("*/summary.csv")):
            with path.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    if row["sample"] == "holdout" and row["feature"] != "all":
                        groups[(timeframe, int(row["horizon"]), row["feature"], row["bucket"])].append(row)
    output = []
    for (timeframe, horizon, feature, bucket), rows in sorted(groups.items()):
        eligible = [row for row in rows if int(row["episode_count"]) >= min_episodes]
        for outcome in OUTCOMES:
            current = [float(row[f"{outcome}_pct"]) for row in eligible]
            baseline = [float(row[f"baseline_{outcome}_pct"]) for row in eligible]
            changes = [a - b for a, b in zip(current, baseline)]
            output.append({"timeframe": timeframe, "horizon": horizon,
                           "feature": feature, "bucket": bucket, "outcome": outcome,
                           "tickers_with_results": len(rows), "tickers_min_episodes": len(eligible),
                           "min_episodes": min_episodes,
                           "positive_delta_tickers": sum(value > 0 for value in changes),
                           "median_delta_pp": round(statistics.median(changes), 2) if changes else "",
                           "median_conditional_pct": round(statistics.median(current), 2) if current else "",
                           "median_baseline_pct": round(statistics.median(baseline), 2) if baseline else ""})
    results.mkdir(parents=True, exist_ok=True)
    with (results / "overview.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--min-episodes", type=int, default=20)
    args = parser.parse_args()
    print(f"overview rows: {len(summarize(args.results, min_episodes=args.min_episodes))}")


if __name__ == "__main__":
    main()
