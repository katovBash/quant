"""Third cycle: extra execution cost sensitivity for EMA12/33 candidates."""

import csv
import json
from pathlib import Path

from src.ema.core.scan_ema import aggregate, backtest, four_hour

ROOT = Path("experiments/.history/legacy-ema/12-33-cross")
SUCCESS = ROOT / "success"
DAILY = ROOT / "execute/research/daily_weekly_monthly"
CACHE = Path("data/candles/moex_scan")


def main():
    universe = {x["SECID"]: x for x in json.loads((DAILY / "universe.json").read_text())}
    candidates = list(csv.DictReader((SUCCESS / "candidates.csv").open()))
    rows = []
    loaded = {}
    for r in candidates:
        s, tf = r["symbol"], r["timeframe"]
        key = (s, tf)
        if key not in loaded:
            if tf in ("1D", "1W", "1M"):
                file = CACHE / f"{s}_24_2022-01-01_2026-10-30.json"
            else:
                file = CACHE / f"{s}_60_2024-01-01_2026-10-30.json"
            raw = json.loads(file.read_text())
            loaded[key] = four_hour(raw) if tf == "4H" else aggregate(raw, tf)
        tick = float(universe[s].get("MINSTEP") or 0)
        # Stress: an extra 0.10% slippage per side and three ticks total.
        result = backtest(loaded[key], 12, 33, "2025-01-01", 5, 10, tick * 3,
                          r["mode"])
        rows.append({"symbol": s, "timeframe": tf, "mode": r["mode"],
                     "base_oos_pct": r["oos_return_pct"],
                     "stress_oos_pct": round(result["net"], 2),
                     "stress_positive": result["net"] > 0})
    path = SUCCESS / "cost_stress.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    long = [r for r in rows if r["mode"] == "long"]
    survivors = [r for r in long if r["stress_positive"]]
    survivors.sort(key=lambda r: r["stress_oos_pct"], reverse=True)
    report = ["# Проверка чувствительности к затратам", "",
              "Для всех строк из `success` повторён период 2025–2026 с дополнительным проскальзыванием 0,10% на сторону и суммарным проскальзыванием 3 тика вместо 1. Комиссия остаётся 0,05% на сторону. Это стресс-сценарий, а не прогноз фактического исполнения.", "",
              f"Long-кандидатов: {len(long)}; с положительной доходностью после стресса: {len(survivors)}. Short и long+short в CSV присутствуют, но стоимость займа и выплаты дивидендов по короткой позиции всё ещё не учтены.", "",
              "| Тикер | Интервал | База 2025–26 | Стресс 2025–26 |",
              "| --- | --- | ---: | ---: |"]
    for r in survivors[:30]:
        report.append(f"| [{r['symbol']}]({r['symbol']}/README.md) | {r['timeframe']} | {r['base_oos_pct']}% | {r['stress_oos_pct']}% |")
    report += ["", "[Все результаты стресса](cost_stress.csv).", ""]
    (SUCCESS / "COST_STRESS.md").write_text("\n".join(report), encoding="utf-8")
    print(f"stress rows={len(rows)}; long survivors={len(survivors)}/{len(long)}")


if __name__ == "__main__":
    main()
