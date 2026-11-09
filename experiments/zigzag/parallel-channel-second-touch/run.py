"""Full-universe parallel-channel second-contact experiment."""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.research.zigzag_run import run_experiment


def compare(result_dir: Path) -> None:
    """Show matched earlier-entry differences without choosing on seen history."""
    yearly = {}
    with (result_dir / "yearly_returns.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["year"] == "2025":
                yearly[(row["symbol"], row["timeframe"], row["variant"])] = float(row["return_pct"])
    months = defaultdict(list)
    with (result_dir / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["start"].startswith("2025-") and row["variant"] != "baseline":
                months[(row["symbol"], row["timeframe"], row["variant"])].append(float(row["pnl_rub"]))
    grouped = defaultdict(list)
    for (symbol, timeframe, variant), annual in yearly.items():
        if not variant.startswith("pc_"):
            continue
        _, preset, source, exit_code = variant.split("_")
        values = months.get((symbol, timeframe, variant), [])
        if len(values) != 12:
            continue
        control = yearly.get((symbol, timeframe, f"tc_{preset}_{source}_{exit_code}"))
        grouped[(timeframe, source, exit_code)].append({
            "annual": annual, "positive_months": sum(value > 0 for value in values),
            "paired_delta": annual - control if control is not None else None})
    rows = []
    for (timeframe, source, exit_code), values in sorted(grouped.items()):
        paired = [item["paired_delta"] for item in values if item["paired_delta"] is not None]
        rows.append({"signal_timeframe": timeframe,
                     "line_source": {"c": "chart", "d": "1D", "w": "1W"}[source],
                     "exit": exit_code, "cells": len(values),
                     "median_2025_net_pct": round(statistics.median(item["annual"] for item in values), 4),
                     "positive_months_pct": round(100 * sum(item["positive_months"] for item in values) /
                                                   (12 * len(values)), 2),
                     "paired_cells": len(paired),
                     "median_delta_vs_third_touch_pp": round(statistics.median(paired), 4)
                     if paired else None})
    result = {"selection_period": "2025 full train year",
              "late_period": "2026 already seen while forming hypothesis",
              "unit": "matched symbol/timeframe/preset/source/exit for fixed targets",
              "rows": rows}
    (result_dir / "parallel_comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path = result_dir / "REPORT.md"
    if path.is_file():
        report = path.read_text(encoding="utf-8")
        heading = "## Второе касание параллельного канала"
        if heading in report:
            report = report.split(heading, 1)[0].rstrip() + "\n"
        lines = [heading, "", "`pc` — вход на втором касании параллельной границы; "
                 "`tc` — прежний вход на третьем касании. Сравнение парное только "
                 "при одинаковом выходе 3% или 5%; выход к противоположной границе "
                 "показан отдельно. Год 2026 уже был просмотрен при формировании идеи. "
                 "После первого полного расчёта обнаружено, что общий селектор выбрал "
                 "контроль `tc`. Допуск ограничен `pc` уже после просмотра результатов; "
                 "это уточнение не является независимым предварительным отбором.", "",
                 "| Сигнал | Линия | Выход | Случаев | Медиана 2025 net | Прибыльных месяцев | Разница к третьему касанию |",
                 "|---|---|---|---:|---:|---:|---:|"]
        for row in rows:
            difference = row["median_delta_vs_third_touch_pp"]
            difference_text = (f"{difference:+.2f} п.п. ({row['paired_cells']})"
                               if difference is not None else "—")
            lines.append(f"| {row['signal_timeframe']} | {row['line_source']} | "
                         f"`{row['exit']}` | {row['cells']} | "
                         f"{row['median_2025_net_pct']:+.2f}% | "
                         f"{row['positive_months_pct']:.1f}% | {difference_text} |")
        path.write_text(report.rstrip() + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    output = experiment / ("smoke" if "--smoke" in sys.argv else "results")
    if "--compare-only" not in sys.argv:
        run_experiment(experiment, smoke="--smoke" in sys.argv)
    compare(output)
