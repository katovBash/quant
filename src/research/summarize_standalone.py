"""Summarize complete standalone research CSVs without promoting any strategy."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

if __package__:
    from .summary_timeframes import update_summary
else:
    from summary_timeframes import update_summary


def number(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def summarize(folder: Path) -> Path:
    result_dir = folder / "results"
    manifest = result_dir / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(manifest)
    lines = [f"# {folder.name}: историческая сводка", "",
             "Это результаты перебора на уже просмотренной истории, **не доказательство будущей прибыли**. "
             "Положительный максимум по тикеру выбран после сравнения вариантов. "
             "Стоимость займа short, дивиденды, реальные лоты и корпоративные события не учтены.", "",
             "[Условия запуска](results/manifest.json) · [покрытие и ошибки](results/progress.csv) · "
             "[полные CSV по каждому тикеру](results/)", ""]
    if folder.name == "rsi-grid-search":
        lines += ["**SFIN:** крупный дивидендный разрыв 25.12.2025 существенно искажает "
                  "результаты long+short, если стратегия держала short до отсечки: "
                  "дивидендная выплата по короткой позиции отсутствует в расчёте. "
                  "Например, в RSI(21) 60/40 на SFIN 1H короткая позиция составляла 221 акцию, "
                  "а неучтённая выплата — 199 342 ₽. Пересчёт с одной этой выплатой: "
                  "+143,05% вместо +173,85%; остальные расходы ещё отсутствуют. См. "
                  "[разбор кандидата](../../strategies/rsi-21-60-40-long-short-1h/README.md).", ""]
    progress_rows = list(csv.DictReader((result_dir / "progress.csv").open(encoding="utf-8")))
    latest_progress = {(row["symbol"], row["timeframe"]): row for row in progress_rows}
    configured_frames = json.loads(manifest.read_text(encoding="utf-8")).get("timeframes", ["1H", "4H", "1D"])
    for timeframe in configured_frames:
        files = sorted((result_dir / timeframe).glob("*.csv")) if (result_dir / timeframe).exists() else []
        rows = []
        for file in files:
            with file.open(encoding="utf-8", newline="") as stream:
                rows.extend(csv.DictReader(stream))
        expected = [row for (symbol, tf), row in latest_progress.items() if tf == timeframe]
        failures = [row for row in expected if row["status"] == "skipped"]
        lines += [f"## {timeframe}", "",
                  f"Проверено тикеров: **{len(files)}**; пропущено или без достаточной истории: **{len(failures)}**; "
                  f"строк вариантов: **{len(rows)}**. Для 15M/30M нужны минутные свечи; "
                  "4H собраны из часовых. Границы свечей могут отличаться от TradingView.", ""]
        if not rows:
            lines += ["Результатов пока нет.", ""]
            continue
        fixed = defaultdict(list)
        for row in rows:
            fixed[(row["variant"], row["mode"])].append(row)
        ranked = []
        for (variant, mode), group in fixed.items():
            returns = [number(row["net_return_pct"]) for row in group]
            excess = [number(row["excess_vs_hold_pp"]) for row in group]
            ranked.append((statistics.median(excess), variant, mode, len(group),
                           statistics.median(returns), sum(value > 0 for value in returns)))
        ranked.sort(reverse=True)
        lines += ["### Одна и та же настройка на разных бумагах", "",
                  "Сортировка по **медианному** превышению над удержанием той же доли акции. "
                  "Это обзор переносимости на просмотренных бумагах, не независимая проверка.", "",
                  "| Вариант | Режим | Тикеров | Медиана доходности | Прибыльных | Медиана сверх удержания |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        for excess, variant, mode, count, median_return, positive in ranked[:5]:
            lines.append(f"| {variant} | {mode} | {count} | {median_return:+.2f}% | {positive} | {excess:+.2f} п.п. |")
        best_by_symbol = {}
        for row in rows:
            trades = int(row["closed_trades"])
            late_trades = int(row["late_trades"])
            net = number(row["net_return_pct"])
            late = number(row["late_return_pct"])
            pf = number(row["profit_factor"])
            dd = number(row["max_drawdown_pct"])
            excess = number(row["excess_vs_hold_pp"])
            if not (trades >= 100 and late_trades >= 30 and net > 0 and late > 0
                    and pf > 1.2 and dd >= -20 and excess > 0):
                continue
            key = row["symbol"]
            if key not in best_by_symbol or net > number(best_by_symbol[key]["net_return_pct"]):
                best_by_symbol[key] = row
        top = sorted(best_by_symbol.values(), key=lambda row: number(row["net_return_pct"]), reverse=True)[:5]
        lines += ["", "### Топ‑5 тикеров после предварительного фильтра", "",
                  "Фильтр: ≥100 закрытых и ≥30 поздних сделок, доходность >0 в обоих периодах, "
                  "PF>1,2, просадка не хуже −20% и превышение удержания. "
                  "Выбрана лучшая строка **по той же истории**; это кандидаты для дальнейшей проверки, не стратегии.", "",
                  "| Тикер | Вариант | Режим | Доходность | Сделки / прибыльные | PF | Поздняя доходность |",
                  "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
        for row in top:
            lines.append(f"| {row['symbol']} | {row['variant']} | {row['mode']} | "
                         f"{number(row['net_return_pct']):+.2f}% | "
                         f"{row['closed_trades']} / {row['winning_trades']} | "
                         f"{number(row['profit_factor']):.2f} | {number(row['late_return_pct']):+.2f}% |")
        if not top:
            lines.append("| Нет строк, прошедших фильтр | — | — | — | — | — | — |")
        lines.append("")
    target = folder / "SUMMARY.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    update_summary(folder)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(summarize(args.folder))


if __name__ == "__main__":
    main()
