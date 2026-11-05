"""Append the same inspectable month matrix to existing specialist reports."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "## Каждый полный месяц · выбранные примеры"


def update(folder: Path) -> bool:
    source = folder / "results/monthly_returns.csv"
    report = folder / "results/REPORT.md"
    if not source.is_file() or not report.is_file():
        return False
    body = report.read_text(encoding="utf-8")
    if MARKER in body or "## Каждый полный месяц" in body:
        return False
    by_case: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    with source.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            try:
                by_case[(row["symbol"], row["timeframe"], row["variant"])][row["start"][:7]] = float(row["return_pct"])
            except (KeyError, ValueError):
                continue
    cases = sorted((item for item in by_case.items() if item[0][2] != "baseline"),
                   key=lambda item: (sum(x > 0 for x in item[1].values()),
                                     sum(item[1].values()), len(item[1])), reverse=True)[:10]
    if not cases:
        return False
    lines = [MARKER, "",
             "Ниже — десять примеров с наибольшим числом прибыльных месяцев "
             "на уже просмотренной истории. Это не независимый отбор. "
             "Все акции, варианты и месяцы: [monthly_returns.csv](monthly_returns.csv).", "",
             "| Акция · интервал · вариант · год | Янв | Фев | Мар | Апр | Май | Июн | Июл | Авг | Сен | Окт | Ноя | Дек |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for (symbol, frame, variant), months in cases:
        years = sorted({stamp[:4] for stamp in months})
        for year in years:
            cells = []
            for month in range(1, 13):
                value = months.get(f"{year}-{month:02d}")
                cells.append(f"{value:+.2f}%" if value is not None else "—")
            lines.append("| " + f"{symbol} · {frame} · `{variant}` · {year} | " + " | ".join(cells) + " |")
    report.write_text(body.rstrip() + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return True


if __name__ == "__main__":
    for protocol in sorted((ROOT / "experiments").rglob("protocol.json")):
        if ".history" not in protocol.parts and update(protocol.parent):
            print(protocol.parent.relative_to(ROOT))
