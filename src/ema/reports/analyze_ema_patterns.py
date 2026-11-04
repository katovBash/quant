"""Second research cycle: check whether a profitable prior year persists."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.ema.core.scan_ema import MODES, backtest

ROOT = Path("experiments/.history/legacy-ema/12-33-cross/execute/research")
CACHE = Path("data/moex_scan")
YEARS = (2023, 2024, 2025, 2026)


def median(values):
    return round(statistics.median(values), 2) if values else 0.0


def main():
    universe = json.loads((ROOT / "daily_weekly_monthly/universe.json").read_text())
    tick = {x["SECID"]: float(x.get("MINSTEP") or 0) for x in universe}
    rows = []
    for symbol in tick:
        path = CACHE / f"{symbol}_24_2022-01-01_2026-10-30.json"
        if not path.exists():
            continue
        bars = json.loads(path.read_text())
        if len(bars) < 100:
            continue
        turnover = statistics.median([b["close"] * b["volume"] for b in bars[-60:]])
        if turnover < 50_000_000:
            continue
        for year in YEARS:
            prefix = [b for b in bars if b["ts"][:4] <= str(year)]
            if not prefix or prefix[-1]["ts"][:4] != str(year):
                continue
            for mode in MODES:
                result = backtest(prefix, 12, 33, f"{year}-01-01", 5, 0, tick[symbol], mode)
                rows.append({"symbol": symbol, "year": year, "mode": mode,
                             "net_return_pct": round(result["net"], 2),
                             "closed_trades": result["trades"],
                             "win_rate_pct": round(100 * result["wins"] / result["trades"], 2)
                             if result["trades"] else "",
                             "turnover_mrub": round(turnover / 1e6, 1)})
    path = ROOT / "yearly_ema_12_33.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    by_key = {(r["symbol"], r["year"], r["mode"]): r for r in rows}
    report = ["# Второй цикл: сохраняется ли прибыльность EMA12/33 в следующем году?", "",
              "Отбор по прошлому году проверен на 86 ликвидных бумагах TQBR (медианный дневной оборот последних 60 баров ≥50 млн ₽). Доходности каждого года посчитаны отдельно с историей EMA до его начала. Открытая позиция на конец года оценена по последней цене, закрытые сделки считаются отдельно. Результаты short не включают стоимость займа и дивиденды.", "",
              "Правило эксперимента: если у тикера за предыдущий год доходность стратегии >0% и ≥2 закрытых сделок, включить его в группу следующего года. Сравнение с остальными бумагами — описательное; сделки портфеля и ребалансировка не моделировались.", "",
              "| Режим | Переход | Отобрано | Медиана доходности следующего года, % | Остальные, % | Доля с плюсом среди отобранных |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    conclusions = []
    for mode in MODES:
        for prev_year, year in ((2023, 2024), (2024, 2025), (2025, 2026)):
            selected, others = [], []
            for symbol in tick:
                past = by_key.get((symbol, prev_year, mode))
                future = by_key.get((symbol, year, mode))
                if not past or not future:
                    continue
                target = selected if past["net_return_pct"] > 0 and past["closed_trades"] >= 2 else others
                target.append(future["net_return_pct"])
            share = round(100 * sum(x > 0 for x in selected) / len(selected), 1) if selected else 0
            report.append(f"| {mode} | {prev_year}→{year} | {len(selected)} | {median(selected):+.2f} | {median(others):+.2f} | {share:.1f}% |")
            if selected and median(selected) <= median(others):
                conclusions.append(f"{mode} {prev_year}→{year}")
    report += ["", "## Вывод по гипотезе", ""]
    if conclusions:
        report.append("Правило `прошлый год был прибыльным` не показало устойчивого преимущества во всех переходах: "
                      + ", ".join(conclusions) + ". Не добавлять его как обязательный фильтр входа.")
    else:
        report.append("Во всех доступных переходах отобранная группа имела более высокую медиану, но три перехода не доказывают устойчивое преимущество. Нужна проверка на следующих годах.")
    report += ["", "## Что проверить дальше", "",
               "1. Разделить 2022–2024 для подбора, 2025 для проверки и будущие данные для окончательного теста; не переносить найденные здесь пороги без нового периода.",
               "2. Повторить расчёт с полной стоимостью short у конкретного брокера, компенсацией дивидендов и списком доступных к заимствованию бумаг.",
               "3. Проверить чувствительность к комиссии, 1–3 тикам проскальзывания и торговле только ликвидными лотами.",
               "4. Проверить корпоративные действия, корректировку дивидендов и полное совпадение настроек с TradingView на VTBR/LKOH.",
               "5. Исследовать трендовый режим более старшей EMA (66/111) и вход после ретеста EMA33, но оценивать по будущему периоду, чтобы избежать подгонки.",
               "6. Проверить результат на уровне портфеля: одновременные сигналы, общий лимит капитала, корреляции и оборот.", "",
               "[Исходные годовые строки](yearly_ema_12_33.csv).", ""]
    (ROOT / "PATTERNS.md").write_text("\n".join(report), encoding="utf-8")
    print(f"yearly rows={len(rows)}; report={ROOT / 'PATTERNS.md'}")


if __name__ == "__main__":
    main()
