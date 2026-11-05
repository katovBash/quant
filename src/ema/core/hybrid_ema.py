"""Backtest the asymmetric EMA6/12 long + EMA12/33 short hypothesis."""

from __future__ import annotations

import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path

from src.ema.core.scan_ema import aggregate, ema, four_hour

ROOT = Path("experiments/.history/legacy-ema/6-12-long-12-33-short")
SOURCE = Path("experiments/.history/legacy-ema/12-33-cross/execute/research")
CACHE = Path("data/candles/moex_scan")


def target_position(e6: list[float], e12: list[float], e33: list[float],
                    signal_index: int, position: int,
                    variant: str = "hybrid") -> int:
    """Return desired side from a confirmed signal bar; 0 means flat."""
    if variant not in ("hybrid", "trend_long", "symmetric_12_33"):
        raise ValueError(variant)
    j = signal_index
    up6_12 = e6[j - 1] <= e12[j - 1] and e6[j] > e12[j]
    down6_12 = e6[j - 1] >= e12[j - 1] and e6[j] < e12[j]
    up12_33 = e12[j - 1] <= e33[j - 1] and e12[j] > e33[j]
    down12_33 = e12[j - 1] >= e33[j - 1] and e12[j] < e33[j]
    if variant == "symmetric_12_33":
        if up12_33:
            return 1
        if down12_33:
            return -1
        return 1 if position > 0 else -1 if position < 0 else 0
    if variant == "trend_long":
        # The 6/12 cross times a long only inside an established 12>33 trend.
        # Both long exit and short entry use 12/33 crossing down.
        if up6_12 and e12[j] > e33[j] and not down12_33:
            return 1
        if down12_33:
            return -1
        if position < 0 and up12_33:
            return 0
        return 1 if position > 0 else -1 if position < 0 else 0
    if up6_12 and down12_33:
        return 0
    if up6_12:
        return 1
    if down12_33:
        return -1
    if (position > 0 and down6_12) or (position < 0 and up12_33):
        return 0
    return 1 if position > 0 else -1 if position < 0 else 0


def backtest(bars: list[dict], start: str, tick: float, borrow_annual_pct: float = 0,
             fee_bps: float = 5, slip_bps: float = 0,
             variant: str = "hybrid", collect_trades: bool = False) -> dict:
    if borrow_annual_pct < 0 or fee_bps < 0 or slip_bps < 0:
        raise ValueError("costs must be nonnegative")
    if len(bars) < 36:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "closed_trades": 0,
                "winning_trades": 0, "long_trades": 0, "short_trades": 0,
                "profit_factor": 0.0, "borrow_rub": 0.0}
    prices = [b["close"] for b in bars]
    e6, e12, e33 = (ema(prices, n) for n in (6, 12, 33))
    fee = fee_bps / 10000
    slip = slip_bps / 10000
    capital = cash = 1_000_000.0
    position = 0
    entry_flow = 0.0
    entry_borrow = 0.0
    borrow_total = 0.0
    trade_pnl = []
    sides = []
    trades = []
    entry_ts = None
    peak = capital
    drawdown = 0.0
    last_close = None
    for i in range(33, len(bars)):
        bar = bars[i]
        if bar["ts"][:10] < start:
            continue
        if last_close is not None and position < 0:
            dt = (datetime.fromisoformat(bar["ts"]) -
                  datetime.fromisoformat(bars[i - 1]["ts"])).total_seconds()
            borrow = -position * bars[i - 1]["close"] * borrow_annual_pct / 100 * dt / (365.25 * 86400)
            cash -= borrow
            borrow_total += borrow
            entry_borrow += borrow
        last_close = bar["close"]
        target = target_position(e6, e12, e33, i - 1, position, variant)
        signal_equity = cash + position * bars[i - 1]["close"]
        qty = math.floor(signal_equity * 0.25 / bars[i - 1]["close"])
        if position and target != (1 if position > 0 else -1):
            if position > 0:
                proceeds = position * max(bar["open"] * (1 - slip) - tick, 0) * (1 - fee)
                cash += proceeds
                pnl = proceeds - entry_flow
                trade_pnl.append(pnl)
                sides.append("long")
            else:
                cover = -position * (bar["open"] * (1 + slip) + tick) * (1 + fee)
                cash -= cover
                pnl = entry_flow - cover - entry_borrow
                trade_pnl.append(pnl)
                sides.append("short")
            if collect_trades:
                trades.append({"entry_ts": entry_ts, "exit_ts": bar["ts"],
                               "side": sides[-1], "pnl_rub": round(pnl, 2)})
            position = 0
            entry_borrow = 0.0
            entry_ts = None
        if position == 0 and target and qty > 0:
            if target > 0:
                cost = qty * (bar["open"] * (1 + slip) + tick) * (1 + fee)
                if cost <= cash:
                    cash -= cost
                    position = qty
                    entry_flow = cost
                    entry_ts = bar["ts"]
            else:
                proceeds = qty * max(bar["open"] * (1 - slip) - tick, 0) * (1 - fee)
                cash += proceeds
                position = -qty
                entry_flow = proceeds
                entry_ts = bar["ts"]
        equity = cash + position * bar["close"]
        peak = max(peak, equity)
        drawdown = min(drawdown, equity / peak - 1)
    final = cash + position * (last_close or bars[-1]["close"])
    wins = sum(p > 0 for p in trade_pnl)
    gross_profit = sum(p for p in trade_pnl if p > 0)
    gross_loss = -sum(p for p in trade_pnl if p < 0)
    result = {"return_pct": round(100 * (final / capital - 1), 2),
            "max_drawdown_pct": round(100 * drawdown, 2),
            "closed_trades": len(trade_pnl), "winning_trades": wins,
            "long_trades": sides.count("long"), "short_trades": sides.count("short"),
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else
            ("inf" if gross_profit else 0.0), "borrow_rub": round(borrow_total, 2)}
    if collect_trades:
        result["trades"] = trades
    return result


def load_bars(symbol: str, timeframe: str) -> list[dict]:
    if timeframe in ("1D", "1W", "1M"):
        path = CACHE / f"{symbol}_24_2022-01-01_2026-10-30.json"
    else:
        path = CACHE / f"{symbol}_60_2024-01-01_2026-10-30.json"
    raw = json.loads(path.read_text())
    return four_hour(raw) if timeframe == "4H" else aggregate(raw, timeframe)


def run_research() -> None:
    universe = json.loads((SOURCE / "daily_weekly_monthly/universe.json").read_text())
    ticks = {x["SECID"]: float(x.get("MINSTEP") or 0) for x in universe}
    original = {}
    for path in (SOURCE / "daily_weekly_monthly/all_results.csv",
                 SOURCE / "intraday/all_results.csv"):
        with path.open(encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if (row["fast"], row["slow"], row["mode"]) in (
                    ("6", "12", "long"), ("12", "33", "short"),
                    ("12", "33", "long_short")):
                    original[row["symbol"], row["timeframe"], row["fast"],
                             row["slow"], row["mode"]] = row
    rows = []
    for symbol in ticks:
        daily = load_bars(symbol, "1D")
        turnover = statistics.median([b["close"] * b["volume"] for b in daily[-60:]]) if daily else 0
        for tf in ("1D", "1W", "1M", "1H", "4H"):
            if tf in ("1H", "4H") and not (CACHE / f"{symbol}_60_2024-01-01_2026-10-30.json").exists():
                continue
            bars = daily if tf == "1D" else load_bars(symbol, tf)
            full_start = "2024-01-01" if tf in ("1H", "4H") else "2022-01-01"
            full = backtest(bars, full_start, ticks[symbol])
            late = backtest(bars, "2025-01-01", ticks[symbol])
            late_borrow20 = backtest(bars, "2025-01-01", ticks[symbol], 20)
            base_long = original.get((symbol, tf, "6", "12", "long"), {})
            base_short = original.get((symbol, tf, "12", "33", "short"), {})
            base_symmetric = original.get((symbol, tf, "12", "33", "long_short"), {})
            rows.append({"symbol": symbol, "timeframe": tf, "bars": len(bars),
                         "median_turnover_mrub": round(turnover / 1e6, 1),
                         "hybrid_return_pct": full["return_pct"],
                         "hybrid_max_drawdown_pct": full["max_drawdown_pct"],
                         "hybrid_trades": full["closed_trades"],
                         "hybrid_wins": full["winning_trades"],
                         "hybrid_long_trades": full["long_trades"],
                         "hybrid_short_trades": full["short_trades"],
                         "hybrid_profit_factor": full["profit_factor"],
                         "late_hybrid_pct": late["return_pct"],
                         "late_hybrid_trades": late["closed_trades"],
                         "late_hybrid_wins": late["winning_trades"],
                         "late_hybrid_borrow20_pct": late_borrow20["return_pct"],
                         "late_6_12_long_pct": base_long.get("oos_return_pct", ""),
                         "late_12_33_short_pct": base_short.get("oos_return_pct", ""),
                         "late_12_33_both_pct": base_symmetric.get("oos_return_pct", ""),
                         "buy_hold_pct": base_long.get("buy_hold_return_pct", ""),
                         "late_buy_hold_pct": base_long.get("oos_buy_hold_pct", "")})
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "execute/results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    selected = sorted((r for r in rows if r["timeframe"] == "1D"
                       and r["bars"] >= 100 and r["median_turnover_mrub"] >= 50
                       and r["hybrid_return_pct"] > max(0, float(r["buy_hold_pct"] or 0))
                       and r["late_hybrid_pct"] > max(0, float(r["late_buy_hold_pct"] or 0))
                       and r["hybrid_trades"] >= 10 and r["late_hybrid_trades"] >= 3
                       and r["late_hybrid_wins"] >= 1
                       and float(r["hybrid_profit_factor"]) > 1
                       and r["hybrid_max_drawdown_pct"] >= -30),
                      key=lambda r: r["late_hybrid_pct"], reverse=True)
    success = ROOT / "success"
    success.mkdir(exist_ok=True)
    with (success / "selected.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    lines = ["# Исторические кандидаты EMA6/12 long + EMA12/33 short", "",
             "Отбор: 1D, оборот ≥50 млн ₽/день, ≥100 баров, положительная доходность и обгон удержания 25% капитала на полном и позднем отрезках, ≥10/3 закрытых сделок, ≥1 прибыльная поздняя сделка, PF>1, просадка не глубже 30%. Сортировка по доходности с 2025-01-01. Это отбор на тех же данных, а не независимая проверка будущей доходности. Базовый short без платы за заём.", "",
             "| Тикер | Поздняя доходность | Полная доходность | Сделок / выигрышных | Поздний результат при 20% годовых за заём |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for r in selected:
        symbol = r["symbol"]
        lines.append(f"| [{symbol}]({symbol}/README.md) | {r['late_hybrid_pct']:+.2f}% | {r['hybrid_return_pct']:+.2f}% | {r['hybrid_trades']} / {r['hybrid_wins']} | {r['late_hybrid_borrow20_pct']:+.2f}% |")
        ticker = success / symbol
        ticker.mkdir(exist_ok=True)
        (ticker / "README.md").write_text(
            f"# {symbol} · EMA6/12 long + EMA12/33 short · 1D\n\n"
            f"[Pine-стратегия](../../execute/strategy.pine) · [Все таймфреймы и метрики](../../execute/results.csv) · [Правила и ограничения](../../README.md).\n\n"
            f"Период данных: 2022-01-01—2026-10-30; поздний отрезок: 2025-01-01—2026-10-30. Сигнал по закрытию, исполнение по открытию следующего бара; 25% капитала, комиссия 0,05% за сторону и 1 тик проскальзывания.\n\n"
            f"| Метрика | Значение |\n| --- | ---: |\n"
            f"| Полная доходность | {r['hybrid_return_pct']:+.2f}% |\n"
            f"| Доходность позднего отрезка | {r['late_hybrid_pct']:+.2f}% |\n"
            f"| Доходность удержания, поздний отрезок | {float(r['late_buy_hold_pct']):+.2f}% |\n"
            f"| Поздняя доходность при условных 20% годовых за заём | {r['late_hybrid_borrow20_pct']:+.2f}% |\n"
            f"| Закрытых сделок / прибыльных | {r['hybrid_trades']} / {r['hybrid_wins']} |\n"
            f"| Лонгов / шортов | {r['hybrid_long_trades']} / {r['hybrid_short_trades']} |\n"
            f"| Максимальная просадка | {r['hybrid_max_drawdown_pct']:.2f}% |\n"
            f"| Profit factor | {r['hybrid_profit_factor']} |\n\n"
            f"Только EMA6/12 long в позднем тесте: {float(r['late_6_12_long_pct']):+.2f}%; только EMA12/33 short: {float(r['late_12_33_short_pct']):+.2f}%; симметричная EMA12/33: {float(r['late_12_33_both_pct']):+.2f}%. Сравнение описательное: варианты выбраны после просмотра истории. Скриншота TradingView именно этой комбинации пока нет; CSV рассчитан локально по MOEX ISS.\n",
            encoding="utf-8")
    (success / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"rows={len(rows)} symbols={len(ticks)}")
    print(f"selected_1d={len(selected)}")
    for r in rows:
        if r["symbol"] in ("VTBR", "LKOH", "PLZL", "VKCO", "POSI", "SELG") and r["timeframe"] == "1D":
            print(r)


if __name__ == "__main__":
    run_research()
