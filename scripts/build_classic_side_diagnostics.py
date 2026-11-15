"""Report long-only and short-only outcomes for each selected classic rule."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.classic_indicator_grid import signals_for_method
from src.research.timeframes import load_research_bars

FAMILIES = {"aroon", "williams", "stoch", "keltner", "ichimoku", "mfi", "cmf", "dmi", "cci"}


def build(family: str) -> list[dict]:
    experiment = next((ROOT / "experiments" / family).glob("*/results/paper_review.json")).parent.parent
    review = json.loads((experiment / "results/paper_review.json").read_text())
    protocol = json.loads((experiment / "protocol.json").read_text())
    rule = review["rule"]
    rows = []
    for item in review["stocks"]:
        symbol = item["symbol"]
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, rule["timeframe"])
        entries, _ = signals_for_method(family, rule["variant"], bars)
        gate = [True] * len(bars)
        for side in (1, -1):
            selected = [entry if entry == side else 0 for entry in entries]
            exits = [-side if entry == -side else 0 for entry in entries]
            result = simulate(bars, selected, gate, gate, 0.0, protocol["start"],
                              fee_bps=protocol["simulator_cost_bps_per_side"],
                              exit_signals=exits)
            trades = result["closed_trades"]
            rows.append({"symbol": symbol, "timeframe": rule["timeframe"],
                         "variant": rule["variant"], "side": "long_only" if side > 0 else "short_only",
                         "full_period_return_pct": result["return_pct"],
                         "closed_trades": trades, "winning_trades": result["winning_trades"],
                         "winning_share_pct": round(100 * result["winning_trades"] / trades, 2) if trades else None,
                         "cost_bps_per_side": protocol["simulator_cost_bps_per_side"]})
    target = experiment / "results/trade_side_summary.csv"
    with target.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary = experiment / "SUMMARY.md"
    text = summary.read_text()
    marker = "\n## Стороны выбранного правила\n"
    if marker in text:
        text = text.split(marker, 1)[0]
    text += marker + "\nДля всех выбранных акций отдельно пересчитаны long и short после модельных расходов. "
    text += "Это диагностика выбранного варианта, а не всей сетки. [Доходность, сделки и доля прибыльных по каждой стороне](results/trade_side_summary.csv).\n"
    summary.write_text(text)
    report = experiment / "results/REPORT.md"
    report_text = report.read_text()
    report_marker = "\n## Long/short выбранного правила\n"
    if report_marker in report_text:
        report_text = report_text.split(report_marker, 1)[0]
    report_text += report_marker + "\nПересчитаны только акции и фиксированная настройка, отобранные для paper trading. "
    report_text += "Доходность за всю доступную историю после 15 б.п. на сторону; стоимость займа short и дивиденды исключены.\n\n"
    report_text += "| Акция | Сторона | Доходность | Сделки | Прибыльных | Доля прибыльных |\n| --- | --- | ---: | ---: | ---: | ---: |\n"
    for row in rows:
        share = "—" if row["winning_share_pct"] is None else f'{row["winning_share_pct"]:.2f}%'
        report_text += f'| {row["symbol"]} | {row["side"]} | {row["full_period_return_pct"]:+.2f}% | {row["closed_trades"]} | {row["winning_trades"]} | {share} |\n'
    report_text += "\n[Машинные результаты отдельно по каждой стороне](trade_side_summary.csv).\n"
    report.write_text(report_text)
    return rows


if __name__ == "__main__":
    for name in sorted(FAMILIES):
        rows = build(name)
        print(name, len(rows))
