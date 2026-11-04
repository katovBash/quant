"""Compare the already configured Turtle stocks on every frozen grid variant."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SELECTION = ROOT / "strategies/dennis-turtle-55-20-1h/selection.json"
REFERENCE = "dennis_turtle_55_20"


def main() -> None:
    symbols = [row["symbol"] for row in json.loads(SELECTION.read_text())["top10"]]
    with (RESULTS / "monthly_case_summary.csv").open(newline="", encoding="utf-8") as stream:
        all_rows = list(csv.DictReader(stream))
    with (RESULTS / "all_variants.csv").open(newline="", encoding="utf-8") as stream:
        trades = {(r["symbol"], r["timeframe"], r["variant"]): int(r["closed_trades"])
                  for r in csv.DictReader(stream)}
    rows = [row for row in all_rows if row["symbol"] in symbols]
    expected = {(symbol, frame) for symbol in symbols for frame in ("1H", "4H", "1D")}
    if {(row["symbol"], row["timeframe"]) for row in rows} != expected:
        raise ValueError("one of the configured Turtle stocks is missing a timeframe")
    with (RESULTS / "top10_all_variants.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) + ["closed_trades"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "closed_trades": trades[row["symbol"], row["timeframe"], row["variant"]]})
    lines = [
        "# Текущие 10 акций Turtle: перебор периодов",
        "",
        "Те же десять акций, которые уже подключены к paper trading по 55/20 на 1H. "
        "Все 19 вариантов и контроль на каждой акции и на 1H, 4H, 1D: "
        "[полная таблица](top10_all_variants.csv). Ни одно рабочее правило не изменено.",
        "",
        "Расходы: эквивалент 15 б.п. на сторону (комиссия 5 + проскальзывание 10), "
        "25% капитала 1 млн ₽ на **каждый независимый счёт**. Дивиденды, корпоративные "
        "события, лоты и стоимость short не учтены. Десять бумаг были ранее выбраны по "
        "результату 55/20 на этой же истории, поэтому сравнение подвержено смещению отбора. "
        "Здесь нет нового независимого подтверждения.",
        "",
        "В колонке «лучший» вариант выбран только для описания увиденной истории: "
        "больше прибыльных месяцев, затем мягче худший месяц и выше общий PnL. "
        "Это не допуск к paper trading.",
        "",
        "| Акция | TF | 55/20: плюс/месяцы | 55/20: весь период | 55/20: сделки | Лучший по месяцам | Плюс/месяцы | Весь период | Сделки |",
        "| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for symbol in symbols:
        for frame in ("1H", "4H", "1D"):
            group = [r for r in rows if r["symbol"] == symbol and r["timeframe"] == frame]
            ref = next(r for r in group if r["variant"] == REFERENCE)
            eligible = [r for r in group if r["variant"] != "baseline"]
            best = max(eligible, key=lambda r: (int(r["profitable_months"]),
                                                float(r["worst_month_pnl_rub"]),
                                                float(r["full_period_pnl_rub"])))
            variant = best["variant"].removeprefix("dennis_turtle_").replace("_", "/")
            lines.append(f"| {symbol} | {frame} | {ref['profitable_months']}/{ref['months']} | "
                         f"{float(ref['full_period_return_pct']):+.2f}% | "
                         f"{trades[symbol,frame,REFERENCE]} | {variant} | "
                         f"{best['profitable_months']}/{best['months']} | "
                         f"{float(best['full_period_return_pct']):+.2f}% | "
                         f"{trades[symbol,frame,best['variant']]} |")
    lines += ["", "## Одни и те же параметры на всех десяти акциях", "",
              "Медиана прибыльных месяцев и доходности по десяти **отдельным** счетам. "
              "Значения доходности не суммируются в результат общего портфеля.", "",
              "| TF | Вариант | Медиана прибыльных месяцев | Медиана доходности |",
              "| --- | --- | ---: | ---: |"]
    for frame in ("1H", "4H", "1D"):
        groups = {}
        for row in rows:
            if row["timeframe"] == frame and row["variant"] != "baseline":
                groups.setdefault(row["variant"], []).append(row)
        ranked = []
        for variant, group in groups.items():
            ranked.append((statistics.median(int(r["profitable_months"]) for r in group),
                           statistics.median(float(r["full_period_return_pct"]) for r in group),
                           variant))
        ranked.sort(reverse=True)
        selected = ranked[:3]
        reference = next(item for item in ranked if item[2] == REFERENCE)
        if reference not in selected:
            selected.append(reference)
        for months, ret, variant in selected:
            lines.append(f"| {frame} | {variant.removeprefix('dennis_turtle_').replace('_','/')} | "
                         f"{months:g}/33 | {ret:+.2f}% |")
    lines += ["", "Полные месячные PnL и просадки доступны в "
              "[общем файле по всем акциям](monthly_returns.csv). "
              "Для выбора новых параметров нужен отдельный тест на новых данных и проверка "
              "корпоративных событий и расходов по short.", ""]
    (RESULTS / "TOP10_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(RESULTS / "TOP10_REVIEW.md")


if __name__ == "__main__":
    main()
