"""Summarize the complete SMA 2..200 sweep without promoting a rule."""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate
from src.research.indicator_library import sma
from src.research.standalone_grid import atr, load_bars

from run import hysteresis_signals

HERE = Path(__file__).resolve().parent
SWEEP = HERE / "results/sma_2_200_sweep.csv"
SUMMARY = HERE / "SUMMARY.md"
EXPECTED = 19701


def fmt(row: dict, nearby: float | None = None) -> str:
    base = (f"| {row['fast']}/{row['slow']} | {row['return_pct']:+.2f}% | "
            f"{row['closed_trades']} | {row['profit_factor']:.3f} | "
            f"{row['max_drawdown_pct']:.2f}%")
    return base + (f" | {nearby:+.2f}% |" if nearby is not None else " |")


def main() -> None:
    with SWEEP.open(newline="", encoding="utf-8") as stream:
        raw = list(csv.DictReader(stream))
    if len(raw) != 2 * EXPECTED:
        raise ValueError(f"incomplete sweep: {len(raw)} of {2 * EXPECTED} rows")
    rows = {}
    for row in raw:
        key = (int(row["fast"]), int(row["slow"]), row["rule"])
        if key in rows:
            raise ValueError(f"duplicate result {key}")
        rows[key] = {"fast": key[0], "slow": key[1], "rule": key[2],
                     "return_pct": float(row["return_pct"]),
                     "closed_trades": int(row["closed_trades"]),
                     "winning_trades": int(row["winning_trades"]),
                     "profit_factor": float(row["profit_factor"]),
                     "max_drawdown_pct": float(row["max_drawdown_pct"])}
    if len(rows) != len(raw):
        raise ValueError("incomplete or duplicated pairs")

    base_rule, filter_rule = "cross", "atr14_hysteresis_0.25"
    filtered = [row for row in rows.values() if row["rule"] == filter_rule]
    baseline = rows[(12, 60, base_rule)]
    unchanged_pair = rows[(12, 60, filter_rule)]

    def neighbors(row):
        fast, slow = row["fast"], row["slow"]
        keys = [(fast + df, slow + ds, filter_rule)
                for df in (-1, 0, 1) for ds in (-1, 0, 1)]
        return [rows[key] for key in keys] if all(key in rows for key in keys) else None

    eligible = []
    for row in filtered:
        original = rows[(row["fast"], row["slow"], base_rule)]
        area = neighbors(row)
        if not area or original["closed_trades"] == 0:
            continue
        reduction = 1 - row["closed_trades"] / original["closed_trades"]
        if (row["closed_trades"] >= 100 and reduction >= 0.20 and
                row["return_pct"] >= original["return_pct"] and
                row["max_drawdown_pct"] >= original["max_drawdown_pct"] - 2):
            eligible.append((statistics.median(x["return_pct"] for x in area), row, reduction))
    eligible.sort(key=lambda item: item[0], reverse=True)
    raw_top = sorted(filtered, key=lambda row: row["return_pct"], reverse=True)[:5]

    lines = ["# Полный перебор SMA · SMLT · 1H", "",
             f"Проверено {EXPECTED:,} пар `2 ≤ fast < slow ≤ 200` для каждого из двух правил; "
             f"всего {len(rows):,} расчёта на сохранённых свечах до 30.10.2026. "
             "Это многократный поиск по уже просмотренным данным, не независимая проверка и не новая стратегия.", "",
             "## Фиксированная пара с графика", "",
             "| Правило | Доходность | Закрытые сделки | PF | Просадка |", "| --- | ---: | ---: | ---: | ---: |",
             f"| SMA12/60 пересечение | {baseline['return_pct']:+.2f}% | {baseline['closed_trades']} | "
             f"{baseline['profit_factor']:.3f} | {baseline['max_drawdown_pct']:.2f}% |",
             f"| SMA12/60 + зона 0,25 ATR | {unchanged_pair['return_pct']:+.2f}% | "
             f"{unchanged_pair['closed_trades']} | {unchanged_pair['profit_factor']:.3f} | "
             f"{unchanged_pair['max_drawdown_pct']:.2f}% |", "",
             "## Максимумы перебора (только ориентир)", "",
             "| SMA fast/slow | Доходность | Закрытые сделки | PF | Просадка |", "| --- | ---: | ---: | ---: | ---: |"]
    lines += [fmt(row) for row in raw_top]
    lines += ["", "## Пары с меньшим числом сделок и устойчивыми соседями", "",
              "Условие отбора задано до просмотра полного результата: ≥100 закрытых сделок; "
              "минимум на 20% меньше сделок, чем пересечение той же пары; доходность не ниже "
              "пересечения; просадка не хуже более чем на 2 п.п. Ранг — медиана доходности "
              "зоны 0,25 ATR по девяти соседним парам (`fast±1`, `slow±1`).", "",
              f"Пар, прошедших численный фильтр: **{len(eligible)}**. Это не доказательство эффекта.", "",
              "| SMA fast/slow | Доходность | Закрытые сделки | PF | Просадка | Медиана соседей |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    lines += [fmt(row, median) for median, row, _ in eligible[:10]]
    if not eligible:
        lines.append("| — | — | — | — | — | — |")
    if eligible:
        bars = load_bars("SMLT", "1H")
        close = [bar["close"] for bar in bars]
        volatility = atr(bars, 14)
        allowed = [True] * len(bars)
        top = eligible[0][1]
        years = (("2024", "2024-01-01", "2025-01-01"),
                 ("2025", "2025-01-01", "2026-01-01"),
                 ("2026 до 30 октября", "2026-01-01", None))
        lines += ["", "## Годовые срезы двух пар с зоной 0,25 ATR", "",
                  "| Пара | Период | Доходность | Закрытые сделки |",
                  "| --- | --- | ---: | ---: |"]
        for fast, slow in ((12, 60), (top["fast"], top["slow"])):
            signals = hysteresis_signals(sma(close, fast), sma(close, slow),
                                         volatility, 0.25)
            for label, start, end in years:
                result = simulate(bars, signals, allowed, allowed, 0.2, start, end)
                lines.append(f"| {fast}/{slow} | {label} | {result['return_pct']:+.2f}% | "
                             f"{result['closed_trades']} |")
        lines += ["", "Лидирующая пара выбрана **после просмотра всех этих данных**. "
                  "Годовые срезы не являются независимым подтверждением и не складываются "
                  "в общую доходность."]
    lines += ["", "## Что проверять дальше", "",
              "1. Не выбирать максимум из 39 402 строк как готовую стратегию. "
              "Сверить соседние параметры и результаты по отдельным годам.",
              "2. Проверить исполнение по биржевому лоту, спред, стоимость займа и дивиденды для short.",
              "3. Зафиксировать одну пару до новых свечей; сравнить её с SMA12/60 на будущем периоде. "
              "Действующий paper setup не менять без нового счёта и явного решения.", ""]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(f"rows={len(rows)} eligible={len(eligible)} summary={SUMMARY}")


if __name__ == "__main__":
    main()
