"""Compare 0.618 with the matched 0.5 midpoint by calendar year."""

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))

from src.research.annual_returns import calendar_years


def main() -> None:
    source = HERE / "results/monthly_returns.csv"
    by_case = defaultdict(list)
    with source.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            parts = row["variant"].split("_")
            if len(parts) != 4 or parts[2] not in ("0.5", "0.618"):
                continue
            by_case[(row["symbol"], row["timeframe"], parts[1], parts[3], parts[2])].append(row)
    comparison = []
    for symbol, frame, wing, tolerance in sorted({key[:4] for key in by_case}):
        control = {year["year"]: year for year in calendar_years(by_case.get(
            (symbol, frame, wing, tolerance, "0.5"), []))}
        golden = {year["year"]: year for year in calendar_years(by_case.get(
            (symbol, frame, wing, tolerance, "0.618"), []))}
        for year in sorted(control.keys() & golden.keys()):
            left, right = control[year], golden[year]
            if (left["first_month"], left["last_month"], left["months"]) != (
                    right["first_month"], right["last_month"], right["months"]):
                continue
            comparison.append({"symbol": symbol, "timeframe": frame, "wing": wing,
                               "tolerance_atr": tolerance, "year": year,
                               "first_month": left["first_month"], "last_month": left["last_month"],
                               "months": left["months"], "complete": right["complete"],
                               "midpoint_return_pct": left["return_pct"],
                               "golden_return_pct": right["return_pct"],
                               "golden_minus_midpoint_pp": round(
                                   right["return_pct"] - left["return_pct"], 2)})
    path = HERE / "results/golden_vs_midpoint_yearly.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)
    grouped = defaultdict(list)
    latest_year = max(item["year"] for item in comparison)
    latest_month = max(item["last_month"] for item in comparison if item["year"] == latest_year)
    for row in comparison:
        if row["complete"] or (row["year"] == latest_year and row["first_month"] == 1
                              and row["last_month"] == latest_month and row["months"] == latest_month):
            grouped[(row["timeframe"], row["year"], row["months"])].append(row)
    summary = []
    for (frame, year, months), rows in sorted(grouped.items()):
        delta = [item["golden_minus_midpoint_pp"] for item in rows]
        summary.append({"timeframe": frame, "year": year, "months": months,
                        "matched": len(rows), "golden_better": sum(value > 0 for value in delta),
                        "median_difference_pp": round(statistics.median(delta), 2),
                        "median_golden_return_pct": round(statistics.median(
                            item["golden_return_pct"] for item in rows), 2),
                        "median_midpoint_return_pct": round(statistics.median(
                            item["midpoint_return_pct"] for item in rows), 2)})
    with (HERE / "results/golden_vs_midpoint_summary.csv").open(
            "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(f"{len(comparison)} matched pair-years; {len(summary)} summary rows")


if __name__ == "__main__":
    main()
