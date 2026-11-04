"""Summarize the completed EMA support/resistance sweep without loading all rows."""

from __future__ import annotations

import csv
import json
import math
import statistics
from array import array
from collections import defaultdict
from pathlib import Path

from src.research.standalone_grid import ROOT

FOLDER = ROOT / "experiments/ema-levels-grid-search"


def number(row: dict, key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return math.nan


def passes(row: dict) -> bool:
    return (number(row, "closed_trades") >= 100 and number(row, "late_trades") >= 30
            and number(row, "net_return_pct") > 0 and number(row, "late_return_pct") > 0
            and number(row, "profit_factor") > 1.2 and number(row, "max_drawdown_pct") >= -20
            and number(row, "excess_vs_hold_pp") > 0)


def main() -> None:
    results = FOLDER / "results"
    manifest = json.loads((results / "manifest.json").read_text(encoding="utf-8"))
    expected = {(symbol, timeframe) for symbol in manifest["symbols"]
                for timeframe in manifest["timeframes"]}
    with (results / "progress.csv").open(encoding="utf-8", newline="") as stream:
        latest = {(row["symbol"], row["timeframe"]): row for row in csv.DictReader(stream)}
    if latest.keys() != expected:
        raise RuntimeError(f"EMA sweep incomplete: {len(latest)}/{len(expected)} pairs")
    groups = defaultdict(lambda: {"returns": array("f"), "excess": array("f"), "positive": 0})
    by_ticker = defaultdict(dict)
    counts = defaultdict(lambda: {"files": 0, "rows": 0})
    for timeframe in manifest["timeframes"]:
        for source in sorted((results / timeframe).glob("*.csv")):
            counts[timeframe]["files"] += 1
            with source.open(encoding="utf-8", newline="") as stream:
                for row in csv.DictReader(stream):
                    counts[timeframe]["rows"] += 1
                    key = timeframe, row["variant"], row["mode"]
                    group = groups[key]
                    ret = number(row, "net_return_pct")
                    group["returns"].append(ret)
                    group["excess"].append(number(row, "excess_vs_hold_pp"))
                    group["positive"] += ret > 0
                    if passes(row):
                        ticker = row["symbol"]
                        existing = by_ticker[timeframe].get(ticker)
                        if existing is None or ret > number(existing, "net_return_pct"):
                            by_ticker[timeframe][ticker] = row
    lines = ["# EMA как поддержка и сопротивление: результаты", "",
             f"Проверены периоды **{manifest['ema_period_min']}–{manifest['ema_period_max']}**, "
             "три ширины зоны и три режима направления. Пересечения двух EMA не используются.", "",
             "Это исторический перебор на просмотренных данных. Лучшие строки подвержены подгонке. "
             "Издержки short, дивиденды и корпоративные события не учтены.", "",
             "[Условия](results/manifest.json) · [Покрытие](results/progress.csv) · "
             "[Описание правила](README.md)", ""]
    for timeframe in manifest["timeframes"]:
        fixed = []
        for (frame, variant, mode), group in groups.items():
            if frame == timeframe and group["returns"]:
                fixed.append((statistics.median(group["excess"]), variant, mode,
                              len(group["returns"]), statistics.median(group["returns"]),
                              group["positive"]))
        fixed.sort(reverse=True)
        lines += [f"## {timeframe}", "",
                  f"Тикеров с историей: **{counts[timeframe]['files']}**; "
                  f"строк: **{counts[timeframe]['rows']}**.", "",
                  "### Одна настройка на разных бумагах", "",
                  "Сортировка по медианному превышению над удержанием. Показаны первые 20 из полного "
                  "перебора; все строки доступны в CSV тикеров.", "",
                  "| Вариант | Режим | Тикеров | Медиана доходности | Прибыльных | Медиана сверх удержания |",
                  "| --- | --- | ---: | ---: | ---: | ---: |"]
        for excess, variant, mode, ticker_count, median_return, positives in fixed[:20]:
            lines.append(f"| `{variant}` | {mode} | {ticker_count} | {median_return:+.2f}% | "
                         f"{positives} | {excess:+.2f} п.п. |")
        lines += ["", "### До пяти тикеров после исторического фильтра", "",
                  "Фильтр: ≥100 закрытых сделок, ≥30 в позднем периоде, прибыль в обоих периодах, "
                  "PF >1,2, просадка не глубже 20% и результат выше удержания. Это не независимая проверка.", "",
                  "| Тикер | Вариант | Режим | Доходность | Сделок / выигрышных | Поздняя доходность | CSV |",
                  "| --- | --- | --- | ---: | ---: | ---: | --- |"]
        selected = sorted(by_ticker[timeframe].values(),
                          key=lambda row: number(row, "net_return_pct"), reverse=True)[:5]
        for row in selected:
            lines.append(f"| {row['symbol']} | `{row['variant']}` | {row['mode']} | "
                         f"{number(row, 'net_return_pct'):+.2f}% | "
                         f"{row['closed_trades']} / {row['winning_trades']} | "
                         f"{number(row, 'late_return_pct'):+.2f}% | "
                         f"[CSV](results/{timeframe}/{row['symbol']}.csv) |")
        if not selected:
            lines.append("| Нет строк | — | — | — | — | — | — |")
        lines.append("")
    (FOLDER / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(FOLDER / "SUMMARY.md")


if __name__ == "__main__":
    main()
