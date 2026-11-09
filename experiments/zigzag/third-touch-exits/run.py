from pathlib import Path
import sys
import csv
import json
import statistics
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.research.zigzag_run import run_experiment


def compare_exits(result_dir: Path) -> None:
    """Compare exit rules on matched entries and the last full train year."""
    by_cell = defaultdict(list)
    with (result_dir / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["variant"] == "baseline":
                continue
            _, preset, source, style, mode = row["variant"].split("_")
            by_cell[(row["symbol"], row["timeframe"], preset, source, style, mode)].append(row)
    metrics = defaultdict(list)
    for cell, rows in by_cell.items():
        train = sorted((r for r in rows if r["start"].startswith("2025-")),
                       key=lambda r: r["start"])
        if len(train) != 12:
            continue
        late = sorted((r for r in rows if r["start"].startswith("2026-")),
                      key=lambda r: r["start"])
        yearly = 100 * (float(train[-1]["ending_equity_rub"]) /
                        float(train[0]["starting_equity_rub"]) - 1)
        late_return = (100 * (float(late[-1]["ending_equity_rub"]) /
                              float(late[0]["starting_equity_rub"]) - 1) if late else None)
        metrics[cell[-1]].append({"cell": cell[:-1], "year_2025_pct": yearly,
                                  "profitable_months_2025": sum(float(r["pnl_rub"]) > 0 for r in train),
                                  "late_2026_pct": late_return,
                                  "late_months": len(late),
                                  "closed_trades_2025": sum(int(r["closed_trades"]) for r in train)})
    controls = {r["cell"]: r["year_2025_pct"] for r in metrics["op"]}
    table = []
    for mode in ("op", "line", "t3", "t5", "t8"):
        matched = [r for r in metrics[mode] if r["cell"] in controls]
        if not matched:
            continue
        table.append({"exit_mode": mode, "matched_cells": len(matched),
                      "median_2025_net_pct": round(statistics.median(r["year_2025_pct"] for r in matched), 4),
                      "median_paired_delta_vs_op_pp": round(statistics.median(
                          r["year_2025_pct"] - controls[r["cell"]] for r in matched), 4),
                      "positive_months_2025_pct": round(100 * sum(
                          r["profitable_months_2025"] for r in matched) / (12 * len(matched)), 2),
                      "median_2026_seen_ytd_pct": round(statistics.median(
                          r["late_2026_pct"] for r in matched if r["late_2026_pct"] is not None), 4)
                          if any(r["late_2026_pct"] is not None for r in matched) else None,
                      "closed_trades_2025": sum(r["closed_trades_2025"] for r in matched)})
    winner = max(table, key=lambda r: r["median_2025_net_pct"]) if table else None
    adopt = bool(winner and winner["median_2025_net_pct"] > 0
                 and winner["median_paired_delta_vs_op_pp"] > 0
                 and winner["median_2026_seen_ytd_pct"] is not None
                 and winner["median_2026_seen_ytd_pct"] >= 0)
    by_source = []
    for source in ("c", "d", "w"):
        for mode in ("op", "line", "t3", "t5", "t8"):
            matched = [r for r in metrics[mode]
                       if r["cell"][3] == source and r["cell"] in controls]
            if not matched:
                continue
            late = [r["late_2026_pct"] for r in matched if r["late_2026_pct"] is not None]
            by_source.append({"line_source": {"c": "chart", "d": "1D", "w": "1W"}[source],
                              "exit_mode": mode, "matched_cells": len(matched),
                              "median_2025_net_pct": round(statistics.median(
                                  r["year_2025_pct"] for r in matched), 4),
                              "positive_months_2025_pct": round(100 * sum(
                                  r["profitable_months_2025"] for r in matched) /
                                  (12 * len(matched)), 2),
                              "median_2026_seen_ytd_pct": round(statistics.median(late), 4)
                              if late else None})
    by_signal_and_source = []
    for timeframe in ("1H", "4H"):
        for source in ("c", "d", "w"):
            options = []
            for mode in ("op", "line", "t3", "t5", "t8"):
                matched = [r for r in metrics[mode]
                           if r["cell"][1] == timeframe and r["cell"][3] == source
                           and r["cell"] in controls]
                if not matched:
                    continue
                late = [r["late_2026_pct"] for r in matched if r["late_2026_pct"] is not None]
                options.append({"signal_timeframe": timeframe,
                                "line_source": {"c": "chart", "d": "1D", "w": "1W"}[source],
                                "exit_mode": mode, "matched_cells": len(matched),
                                "median_2025_net_pct": round(statistics.median(
                                    r["year_2025_pct"] for r in matched), 4),
                                "positive_months_2025_pct": round(100 * sum(
                                    r["profitable_months_2025"] for r in matched) /
                                    (12 * len(matched)), 2),
                                "median_2026_seen_ytd_pct": round(statistics.median(late), 4)
                                if late else None})
            if options:
                by_signal_and_source.append(max(options, key=lambda row: row["median_2025_net_pct"]))
    (result_dir / "exit_comparison.json").write_text(json.dumps({
        "selection_period": "2025 full train year",
        "late_period": "2026 seen history; diagnostic only",
        "unit": "matched symbol/timeframe/preset/line-source/entry-style",
        "ranked_by": "median_2025_net_pct",
        "exit_modes": table,
        "by_line_source": by_source,
        "best_by_signal_timeframe_and_line_source": by_signal_and_source,
        "best_historical_exit": winner["exit_mode"] if winner else None,
        "adoption_recommended": adopt,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = result_dir / "REPORT.md"
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8")
        heading = "## Источник линии: график, 1D и 1W"
        if heading in report:
            report = report.split(heading, 1)[0].rstrip() + "\n"
        lines = [heading, "",
                 "1D и 1W здесь — закрытые старшие свечи, по которым строится линия. "
                 "Сигнал и исполнение остаются на 1H или 4H. Ниже для каждой пары "
                 "показан лучший исторический выход по медиане полного 2025 года; "
                 "2026 уже был просмотрен и служит только диагностикой.", "",
                 "| Сделка | Источник линии | Выход | Случаев | Медиана 2025 после расходов | Прибыльных месяцев 2025 | Медиана 2026 YTD |",
                 "|---|---|---|---:|---:|---:|---:|"]
        for row in by_signal_and_source:
            late = row["median_2026_seen_ytd_pct"]
            late_text = f"{late:+.2f}%" if late is not None else "—"
            source_label = "текущий" if row["line_source"] == "chart" else row["line_source"]
            lines.append(f"| {row['signal_timeframe']} | {source_label} | "
                         f"`{row['exit_mode']}` | {row['matched_cells']} | "
                         f"{row['median_2025_net_pct']:+.2f}% | "
                         f"{row['positive_months_2025_pct']:.2f}% | "
                         f"{late_text} |")
        report_path.write_text(report.rstrip() + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    smoke = "--smoke" in sys.argv
    run_experiment(experiment, smoke=smoke)
    compare_exits(experiment / ("smoke" if smoke else "results"))
