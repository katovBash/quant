"""Summarize the frozen entry-only grid against the same-symbol 55/20 control."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "results/all_variants.csv"
OUT = HERE / "results"
VARIANTS = ["baseline", "entry_only_15", "entry_only_20", "entry_only_30",
            "entry_only_40", "entry_only_55", "entry_only_70"]


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in rows:
        groups[(row["timeframe"], row["variant"])].append(row)
    summary = []
    for timeframe in ("1D", "1H", "4H"):
        control = {row["symbol"]: row for row in groups[(timeframe, "baseline")]}
        for variant in VARIANTS:
            sample = groups[(timeframe, variant)]
            values = [float(row["net_return_pct"]) for row in sample]
            summary.append({
                "timeframe": timeframe, "variant": variant, "symbols": len(sample),
                "profitable_symbols": sum(value > 0 for value in values),
                "median_full_return_pct": round(statistics.median(values), 2),
                "median_profitable_months": statistics.median(int(row["positive_months"]) for row in sample),
                "median_closed_trades": statistics.median(int(row["closed_trades"]) for row in sample),
                "median_max_drawdown_pct": round(statistics.median(float(row["max_drawdown_pct"]) for row in sample), 2),
                "beats_control_symbols": sum(float(row["net_return_pct"]) > float(control[row["symbol"]]["net_return_pct"])
                                             for row in sample),
            })
    with (OUT / "comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    lines = ["# Только линии входа Turtle: сравнение с 55/20", "",
             "`baseline` — вход 55 и отдельный выход 20. `entry_only_N` — верхний/нижний канал входа N, "
             "без отдельного канала выхода: позиция разворачивается только по противоположному сигналу входа.", "",
             "Сравнение на тех же свечах и модели расходов 15 б.п. на сторону. Все медианы считаются по отдельным "
             "бумагам с независимым капиталом 1 млн ₽; это не доходность общего портфеля. "
             "Прибыльные месяцы относятся к полным календарным месяцам. История уже просмотрена, "
             "корпоративные события учтены неполно: `REVIEW_ONLY`.", "",
             "| Интервал | Вариант | Бумаг | Прибыльных бумаг | Медиана за весь период | Медиана прибыльных месяцев | Медиана сделок | Медиана макс. просадки | Выше контроля |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summary:
        lines.append(f"| {row['timeframe']} | `{row['variant']}` | {row['symbols']} | "
                     f"{row['profitable_symbols']} | {row['median_full_return_pct']:+.2f}% | "
                     f"{row['median_profitable_months']:g} | {row['median_closed_trades']:g} | "
                     f"{row['median_max_drawdown_pct']:.2f}% | {row['beats_control_symbols']} |")
    lines += ["", "Исходные данные: [все варианты](all_variants.csv), "
              "[каждый месяц](monthly_returns.csv), [проверка полноты](validation.json).", ""]
    (OUT / "COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
