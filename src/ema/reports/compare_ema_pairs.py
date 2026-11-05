"""Summarize 45 EMA pairs across liquid stocks on 1D, by direction."""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path("experiments/.history/legacy-ema/12-33-cross/execute/research")


def main():
    path = ROOT / "daily_weekly_monthly/all_results.csv"
    universe = json.loads((ROOT / "daily_weekly_monthly/universe.json").read_text())
    liquid = set()
    for item in universe:
        s = item["SECID"]
        file = Path(f"data/candles/moex_scan/{s}_24_2022-01-01_2026-10-30.json")
        if not file.exists():
            continue
        bars = json.loads(file.read_text())
        if bars and statistics.median([b["close"] * b["volume"] for b in bars[-60:]]) >= 50_000_000:
            liquid.add(s)
    groups = defaultdict(lambda: [0, 0, []])
    with path.open(encoding="utf-8") as file:
        for r in csv.DictReader(file):
            if r["timeframe"] != "1D" or r["symbol"] not in liquid:
                continue
            key = (r["mode"], int(r["fast"]), int(r["slow"]))
            g = groups[key]
            if r["status"] != "insufficient_history":
                g[0] += 1
            if (r["status"] == "candidate" and int(r["oos_winning_trades"]) >= 1
                    and float(r["excess_return_pp"]) > 0
                    and float(r["oos_excess_pp"]) > 0):
                g[1] += 1
                g[2].append(float(r["oos_return_pct"]))
    report = ["# Сравнение 45 пар EMA на ликвидных акциях, 1D", "",
              f"Всего ликвидных тикеров: {len(liquid)}. В таблице показано число бумаг, прошедших те же критерии, что и `success`: положительная доходность и превышение удержания на полном и позднем периодах, ≥10/3 закрытых сделок, ≥1 прибыльная поздняя сделка, profit factor >1, просадка не глубже 30%. Short без стоимости займа.", "",
              "Это **поиск по 45 комбинациям**; большее число совпадений не доказывает, что одна пара лучше в будущем. Длинные EMA часто имеют меньше сделок и недостаточную историю.", ""]
    for mode in ("long", "short", "long_short"):
        report += [f"## {mode}", "",
                   "| EMA | Бумаг с историей | Прошли фильтр | Медиана поздней доходности среди прошедших |",
                   "| --- | ---: | ---: | ---: |"]
        ranked = sorted(((k, v) for k, v in groups.items() if k[0] == mode),
                        key=lambda kv: (kv[1][1], statistics.median(kv[1][2]) if kv[1][2] else -999),
                        reverse=True)
        for (direction, fast, slow), (eligible, count, returns) in ranked[:15]:
            med = f"{statistics.median(returns):+.2f}%" if returns else "—"
            report.append(f"| {fast}/{slow} | {eligible} | {count} | {med} |")
        report.append("")
    report += ["[Полные строки для всех пар](daily_weekly_monthly/all_results.csv).", ""]
    (ROOT / "PAIR_COMPARISON.md").write_text("\n".join(report), encoding="utf-8")
    print(f"liquid={len(liquid)}; pairs={len(groups)}")


if __name__ == "__main__":
    main()
