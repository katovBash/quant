"""Rerun the fixed Turtle grid for SFIN with a dated dividend snapshot."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from run import CACHE, HERE, PROTOCOL, evaluate
from src.research.corporate_actions import dividends_for, load_dividend_snapshot
from src.research.timeframes import load_research_bars

EVENTS = HERE.parents[2] / "data/dividends/sfin_2026-11-04.json"
OUTPUT = HERE / "results/corporate_sensitivity"
FIELDS = ("symbol", "timeframe", "variant", "original_return_pct", "dividend_return_pct",
          "change_pp", "original_pnl_rub", "dividend_pnl_rub", "original_positive_months",
          "dividend_positive_months", "closed_trades_original", "closed_trades_dividend")


def main() -> None:
    snapshot, digest = load_dividend_snapshot(EVENTS)
    rows = []
    for timeframe in PROTOCOL["signal_timeframes"]:
        bars = load_research_bars(CACHE, "SFIN", timeframe)
        dividends = dividends_for(snapshot, "SFIN", bars)
        original = {row["variant"]: row for row in evaluate("SFIN", timeframe, bars)[0]}
        adjusted = {row["variant"]: row for row in evaluate(
            "SFIN", timeframe, bars, dividends_per_share=dividends)[0]}
        for variant, before in original.items():
            after = adjusted[variant]
            rows.append({
                "symbol": "SFIN", "timeframe": timeframe, "variant": variant,
                "original_return_pct": before["net_return_pct"],
                "dividend_return_pct": after["net_return_pct"],
                "change_pp": round(after["net_return_pct"] - before["net_return_pct"], 2),
                "original_pnl_rub": before["pnl_rub"], "dividend_pnl_rub": after["pnl_rub"],
                "original_positive_months": before["positive_months"],
                "dividend_positive_months": after["positive_months"],
                "closed_trades_original": before["closed_trades"],
                "closed_trades_dividend": after["closed_trades"]})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "all_variants.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "manifest.json").write_text(json.dumps({
        "source_candle_snapshot": PROTOCOL["source_snapshot"],
        "dividend_snapshot_date": snapshot["snapshot_date"],
        "dividend_sha256": digest,
        "covered_symbol": "SFIN", "covered_events": len(snapshot["events"]),
        "coverage": "SFIN cash dividends only; other corporate events and other symbols unverified",
        "paper_trading_changed": False,
        "cost_model": PROTOCOL["cost_status"]}, ensure_ascii=False, indent=2) + "\n")
    selected_symbols = [item["symbol"] for item in json.loads((HERE.parents[2] /
        "strategies/dennis-turtle-55-20-1h/selection.json").read_text(encoding="utf-8"))["top10"]]
    with (HERE / "results/all_variants.csv").open(newline="", encoding="utf-8") as stream:
        after_costs = {item["symbol"]: item for item in csv.DictReader(stream)
                       if item["symbol"] in selected_symbols and item["timeframe"] == "1H"
                       and item["variant"] == "dennis_turtle_55_20"}
    sf_adjusted = next(item for item in rows if item["timeframe"] == "1H"
                       and item["variant"] == "dennis_turtle_55_20")
    dashboard = {"source": "turtle-period-grid fixed 55/20 grid; 15 bps per side",
                 "dividend_scope": "SFIN five cash dividends only; splits and other symbols unverified",
                 "symbols": {symbol: {
                     "after_costs_return_pct": float(after_costs[symbol]["net_return_pct"]),
                     "after_costs_closed_trades": int(after_costs[symbol]["closed_trades"]),
                     **({"sfin_dividend_sensitivity_return_pct": sf_adjusted["dividend_return_pct"]}
                        if symbol == "SFIN" else {})}
                     for symbol in selected_symbols}}
    (HERE / "results/current_turtle_55_20.json").write_text(
        json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selected = [row for row in rows if row["variant"] == "dennis_turtle_55_20"]
    report = ["# Turtle 55/20 · SFIN · чувствительность к дивидендам", "",
              "Пересчёт с теми же свечами и параметрами. Дивиденды начислены длинной позиции и списаны с короткой на первой свече даты фиксации реестра. Исторические сигналы не менялись. Виртуальные счета не затронуты.", "",
              f"Снимок событий: [dividends.json](../../../../data/dividends/sfin_2026-11-04.json), SHA-256 `{digest}`. Источник сумм и дат указан у каждой записи. Покрыты только пять выплат SFIN; сплиты, иные корпоративные события и выплаты других бумаг не проверены.", "",
              "| Таймфрейм | Без дивидендов | С дивидендами | Разница | Прибыльные месяцы до → после | Сделки до → после |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in selected:
        report.append(f"| {row['timeframe']} | {row['original_return_pct']:+.2f}% | "
                      f"{row['dividend_return_pct']:+.2f}% | {row['change_pp']:+.2f} п.п. | "
                      f"{row['original_positive_months']} → {row['dividend_positive_months']} | "
                      f"{row['closed_trades_original']} → {row['closed_trades_dividend']} |")
    report.extend(["", "[Все 19 вариантов и контроль](all_variants.csv). Результат является анализом чувствительности: отбор SFIN и параметров сделан по ранее просмотренной истории, так что это не независимая проверка будущей доходности.", ""])
    (OUTPUT / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
