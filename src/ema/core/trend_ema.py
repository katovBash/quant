"""Research EMA6/12 long timing inside the EMA12>EMA33 regime."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.ema.core.hybrid_ema import backtest, load_bars

ROOT = Path("experiments/.history/legacy-ema/6-12-long-12-33-short/execute/variants/trend-long")
BASE = Path("experiments/.history/legacy-ema/6-12-long-12-33-short/execute/results.csv")
SCANNED = Path("experiments/.history/legacy-ema/12-33-cross/execute/research")


def run_research() -> None:
    ticks = {x["SECID"]: float(x.get("MINSTEP") or 0) for x in json.loads(
        (SCANNED / "daily_weekly_monthly/universe.json").read_text())}
    with BASE.open(encoding="utf-8") as file:
        base_rows = list(csv.DictReader(file))
    rows = []
    for base in base_rows:
        symbol, tf = base["symbol"], base["timeframe"]
        bars = load_bars(symbol, tf)
        tick = ticks[symbol]
        full_start = "2024-01-01" if tf in ("1H", "4H") else "2022-01-01"
        full = backtest(bars, full_start, tick, variant="trend_long")
        late = backtest(bars, "2025-01-01", tick, variant="trend_long")
        stress = backtest(bars, "2025-01-01", tick, 20, variant="trend_long")
        rows.append({"symbol": symbol, "timeframe": tf, "bars": len(bars),
                     "median_turnover_mrub": base["median_turnover_mrub"],
                     "return_pct": full["return_pct"],
                     "max_drawdown_pct": full["max_drawdown_pct"],
                     "closed_trades": full["closed_trades"],
                     "winning_trades": full["winning_trades"],
                     "long_trades": full["long_trades"],
                     "short_trades": full["short_trades"],
                     "profit_factor": full["profit_factor"],
                     "late_return_pct": late["return_pct"],
                     "late_trades": late["closed_trades"],
                     "late_wins": late["winning_trades"],
                     "late_borrow20_pct": stress["return_pct"],
                     "late_6_12_long_12_33_short_pct": base["late_hybrid_pct"],
                     "late_12_33_both_pct": base["late_12_33_both_pct"],
                     "buy_hold_pct": base["buy_hold_pct"],
                     "late_buy_hold_pct": base["late_buy_hold_pct"]})
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "execute/results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    selected = sorted((r for r in rows if r["timeframe"] == "1D"
                       and int(r["bars"]) >= 100
                       and float(r["median_turnover_mrub"]) >= 50
                       and float(r["return_pct"]) > max(0, float(r["buy_hold_pct"] or 0))
                       and float(r["late_return_pct"]) > max(0, float(r["late_buy_hold_pct"] or 0))
                       and int(r["closed_trades"]) >= 10
                       and int(r["late_trades"]) >= 3 and int(r["late_wins"]) >= 1
                       and float(r["profit_factor"]) > 1
                       and float(r["max_drawdown_pct"]) >= -30),
                      key=lambda r: float(r["late_return_pct"]), reverse=True)
    success = ROOT / "success"
    success.mkdir(exist_ok=True)
    with (success / "selected.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    lines = ["# Исторические кандидаты: 6/12 long в тренде 12>33, short по 12/33", "",
             "Поздний период = 01.01.2025—30.10.2026. Предыдущая связка = long при пересечении EMA6/12 вверх, выход при пересечении вниз; short при пересечении EMA12/33 вниз, выход при пересечении вверх. В этом списке показана доходность каждой стратегии на одном и том же тикере за поздний период.", "",
             "Отбор: 1D, оборот ≥50 млн ₽, ≥100 баров, доходность выше нуля и удержания на полном и позднем отрезках, ≥10/3 закрытых сделок, ≥1 прибыльная поздняя сделка, PF>1, просадка ≥−30%. Сортировка по поздней доходности. Отбор на известных данных не прогнозирует результат на новых данных.", "",
             "| Тикер | Этот вариант, 2025–2026 | Этот вариант, весь период | Сделок / выигрышных | EMA6/12 long + EMA12/33 short, 2025–2026 | EMA12/33 long+short, 2025–2026 |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for r in selected:
        symbol = r["symbol"]
        lines.append(f"| [{symbol}]({symbol}/README.md) | {float(r['late_return_pct']):+.2f}% | {float(r['return_pct']):+.2f}% | {r['closed_trades']} / {r['winning_trades']} | {float(r['late_6_12_long_12_33_short_pct']):+.2f}% | {float(r['late_12_33_both_pct']):+.2f}% |")
        ticker = success / symbol
        ticker.mkdir(exist_ok=True)
        (ticker / "README.md").write_text(
            f"# {symbol} · EMA6/12 long при EMA12>EMA33; EMA12/33 short · 1D\n\n"
            f"[Pine-скрипт](../../execute/strategy.pine) · [Правила исследования](../../README.md) · [Полный CSV](../../execute/results.csv).\n\n"
            f"Период 2022-01-01—2026-10-30; поздний отрезок 2025-01-01—2026-10-30. Вход по закрытой свече, исполнение на открытии следующей. Доля 25%, комиссия 0,05% за сторону, проскальзывание 1 тик.\n\n"
            f"| Метрика | Значение |\n| --- | ---: |\n"
            f"| Полная доходность | {float(r['return_pct']):+.2f}% |\n"
            f"| Поздняя доходность | {float(r['late_return_pct']):+.2f}% |\n"
            f"| При условных 20% годовых за заём, поздняя | {float(r['late_borrow20_pct']):+.2f}% |\n"
            f"| Закрытые / прибыльные сделки | {r['closed_trades']} / {r['winning_trades']} |\n"
            f"| Лонги / шорты | {r['long_trades']} / {r['short_trades']} |\n"
            f"| Profit factor | {r['profit_factor']} |\n"
            f"| Максимальная просадка | {float(r['max_drawdown_pct']):.2f}% |\n"
            f"| Удержание 25%, позднее | {float(r['late_buy_hold_pct']):+.2f}% |\n"
            f"| EMA6/12 long + EMA12/33 short, 2025–2026 | {float(r['late_6_12_long_12_33_short_pct']):+.2f}% |\n"
            f"| EMA12/33 long+short, позднее | {float(r['late_12_33_both_pct']):+.2f}% |\n\n"
            f"Это локальный тест MOEX ISS. Скриншота TradingView для этого варианта нет; он требует отдельной сверки сделок.\n",
            encoding="utf-8")
    (success / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rows={len(rows)} selected_1d={len(selected)}")
    for r in rows:
        if r["symbol"] in ("VTBR", "LKOH", "GAZP") and r["timeframe"] == "1D":
            print(r)


if __name__ == "__main__":
    run_research()
