"""Show actual timeframe coverage in historical experiment summaries.

The table is derived from result CSVs and progress records. Missing intraday
data never becomes a synthetic performance result.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


TIMEFRAMES = ("15M", "30M", "1H", "4H", "1D")
START = "<!-- timeframe-coverage:start -->"
END = "<!-- timeframe-coverage:end -->"


def coverage_block(folder: Path) -> str:
    results = folder / "results"
    progress = results / "progress.csv"
    latest: dict[tuple[str, str], dict[str, str]] = {}
    if progress.exists():
        with progress.open(encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                latest[(row["symbol"], row["timeframe"])] = row

    lines = [START, "## Покрытие таймфреймов", "",
             "Показатели ниже относятся только к интервалам с готовыми CSV или CSV.gz. "
             "Отсутствие результата не означает нулевую доходность.", "",
             "| Таймфрейм | Тикеров с результатом | Статус |",
             "| --- | ---: | --- |"]
    for timeframe in TIMEFRAMES:
        directory = results / timeframe
        files = [*directory.glob("*.csv"), *directory.glob("*.csv.gz")] if directory.exists() else []
        completed = len(files)
        statuses = [row["status"] for (symbol, tf), row in latest.items() if tf == timeframe]
        if completed:
            status = "есть исторические результаты"
        elif timeframe in ("15M", "30M"):
            status = "ожидает минутных свечей" if not statuses or all(
                value in ("missing_cache", "skipped") for value in statuses
            ) else "запуск без готовых результатов"
        elif statuses:
            status = "запуск без готовых результатов"
        else:
            status = "не запускался"
        lines.append(f"| {timeframe} | {completed} | {status} |")
    lines += ["", "15M и 30M строятся из минутных свечей. "
              "[Проверка наличия минутных данных](../../data/candles/moex_scan/minute_coverage.json).", END]
    return "\n".join(lines)


def update_summary(folder: Path) -> Path:
    summary = folder / "SUMMARY.md"
    if not summary.exists():
        raise FileNotFoundError(summary)
    existing = summary.read_text(encoding="utf-8")
    block = coverage_block(folder)
    if START in existing or END in existing:
        if existing.count(START) != 1 or existing.count(END) != 1:
            raise ValueError(f"Unbalanced coverage markers: {summary}")
        updated = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n*",
                         block + "\n\n", existing, flags=re.S)
    else:
        first_line, _, rest = existing.partition("\n")
        updated = f"{first_line}\n\n{block}\n\n{rest.lstrip()}"
    summary.write_text(updated, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    args = parser.parse_args()
    for folder in args.folders:
        print(update_summary(folder))


if __name__ == "__main__":
    main()
