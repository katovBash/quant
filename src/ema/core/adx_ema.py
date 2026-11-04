"""Compare EMA12/33 long-short with ADX(14) entry filters on cached MOEX bars."""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Callable

from src.ema.core.scan_ema import aggregate, ema, four_hour

ROOT = Path("experiments/.history/legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/adx-filter")
OUTPUT = ROOT / "execute"
TICKERS = OUTPUT / "research/tickers"
SUCCESS = ROOT / "success"
CACHE = Path("data/moex_scan")
SCAN = Path("experiments/.history/legacy-ema/12-33-cross/execute/research")
THRESHOLDS = (0, 20, 25)
TIMEFRAMES = ("1D", "1W", "1M", "1H", "4H")


def rma(values: list[float], length: int) -> list[float]:
    """Wilder smoothing: first value is the mean of the first valid window."""
    out = [math.nan] * len(values)
    window = []
    for i, value in enumerate(values):
        if not math.isfinite(value):
            continue
        if len(window) < length:
            window.append(value)
            if len(window) == length:
                out[i] = sum(window) / length
        else:
            out[i] = (out[i - 1] * (length - 1) + value) / length
    return out


def adx(bars: list[dict], length: int = 14) -> list[float]:
    tr, plus_dm, minus_dm = [], [], []
    for i, bar in enumerate(bars):
        if i == 0:
            tr.append(bar["high"] - bar["low"])
            plus_dm.append(0.0)
            minus_dm.append(0.0)
            continue
        prev = bars[i - 1]
        up = bar["high"] - prev["high"]
        down = prev["low"] - bar["low"]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(bar["high"] - bar["low"],
                      abs(bar["high"] - prev["close"]),
                      abs(bar["low"] - prev["close"])))
    atr = rma(tr, length)
    plus = rma(plus_dm, length)
    minus = rma(minus_dm, length)
    dx = []
    for a, p, m in zip(atr, plus, minus):
        if not math.isfinite(a) or a <= 0:
            dx.append(math.nan)
            continue
        pdi, mdi = 100 * p / a, 100 * m / a
        dx.append(100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0.0)
    return rma(dx, length)


def load_bars(symbol: str, timeframe: str) -> list[dict]:
    if timeframe in ("1D", "1W", "1M"):
        path = CACHE / f"{symbol}_24_2022-01-01_2026-10-30.json"
    else:
        path = CACHE / f"{symbol}_60_2024-01-01_2026-10-30.json"
    raw = json.loads(path.read_text())
    if timeframe == "4H":
        return four_hour(raw)
    return aggregate(raw, timeframe)


def backtest(bars: list[dict], adx_values: list[float], threshold: int,
             start: str, tick: float, fee_bps: float = 5,
             entry_filter: Callable[[int, int], bool] | None = None) -> dict:
    """Close every opposite EMA cross; ADX gates only a new entry."""
    if threshold not in THRESHOLDS:
        raise ValueError(threshold)
    if not bars:
        return {"return_pct": 0.0, "max_drawdown_pct": 0.0, "closed_trades": 0,
                "winning_trades": 0, "long_trades": 0, "short_trades": 0,
                "long_wins": 0, "short_wins": 0, "profit_factor": 0.0,
                "skipped_entries": 0, "final_side": "flat"}
    prices = [bar["close"] for bar in bars]
    fast, slow = ema(prices, 12), ema(prices, 33)
    capital = cash = 1_000_000.0
    fee = fee_bps / 10_000
    position = 0
    entry_flow = 0.0
    pnls: list[float] = []
    sides: list[str] = []
    skipped = 0
    peak = capital
    max_drawdown = 0.0
    last_close = None
    for i in range(33, len(bars)):
        bar = bars[i]
        if bar["ts"][:10] < start:
            continue
        previous = bars[i - 1]
        last_close = bar["close"]
        cross_up = fast[i - 2] <= slow[i - 2] and fast[i - 1] > slow[i - 1]
        cross_down = fast[i - 2] >= slow[i - 2] and fast[i - 1] < slow[i - 1]
        desired = 1 if cross_up else -1 if cross_down else None
        if desired is not None:
            equity_at_signal = cash + position * previous["close"]
            qty = math.floor(equity_at_signal * 0.25 / previous["close"])
            allowed = (entry_filter(i - 1, desired) if entry_filter is not None else
                       threshold == 0 or (math.isfinite(adx_values[i - 1]) and
                                          adx_values[i - 1] >= threshold))
            if position and (position > 0) != (desired > 0):
                if position > 0:
                    proceeds = position * max(bar["open"] - tick, 0) * (1 - fee)
                    cash += proceeds
                    pnl = proceeds - entry_flow
                    sides.append("long")
                else:
                    cover = -position * (bar["open"] + tick) * (1 + fee)
                    cash -= cover
                    pnl = entry_flow - cover
                    sides.append("short")
                pnls.append(pnl)
                position = 0
            if position == 0 and qty > 0:
                if not allowed:
                    skipped += 1
                elif desired > 0:
                    cost = qty * (bar["open"] + tick) * (1 + fee)
                    if cost <= cash:
                        cash -= cost
                        position = qty
                        entry_flow = cost
                else:
                    proceeds = qty * max(bar["open"] - tick, 0) * (1 - fee)
                    cash += proceeds
                    position = -qty
                    entry_flow = proceeds
        equity = cash + position * bar["close"]
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1)
    final_equity = cash + position * (last_close or bars[-1]["close"])
    profits = sum(p for p in pnls if p > 0)
    losses = -sum(p for p in pnls if p < 0)
    long_pnls = [p for p, side in zip(pnls, sides) if side == "long"]
    short_pnls = [p for p, side in zip(pnls, sides) if side == "short"]
    return {"return_pct": round(100 * (final_equity / capital - 1), 2),
            "max_drawdown_pct": round(100 * max_drawdown, 2),
            "closed_trades": len(pnls), "winning_trades": sum(p > 0 for p in pnls),
            "long_trades": len(long_pnls), "short_trades": len(short_pnls),
            "long_wins": sum(p > 0 for p in long_pnls),
            "short_wins": sum(p > 0 for p in short_pnls),
            "profit_factor": round(profits / losses, 3) if losses else
            ("inf" if profits else 0.0), "skipped_entries": skipped,
            "final_side": "long" if position > 0 else "short" if position < 0 else "flat"}


def main() -> None:
    daily_universe = json.loads((SCAN / "daily_weekly_monthly/universe.json").read_text())
    intraday_universe = json.loads((SCAN / "intraday/universe.json").read_text())
    ticks = {row["SECID"]: float(row.get("MINSTEP") or 0) for row in daily_universe}
    liquid = {row["SECID"] for row in intraday_universe}
    rows = []
    errors = []
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for entry in daily_universe:
        symbol = entry["SECID"]
        try:
            daily_bars = load_bars(symbol, "1D")
            median_turnover = (statistics.median(
                bar["volume"] * bar["close"] for bar in daily_bars)
                if daily_bars else 0.0)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"symbol": symbol, "timeframe": "1D", "error": str(exc)})
            continue
        for timeframe in TIMEFRAMES:
            if timeframe in ("1H", "4H") and symbol not in liquid:
                continue
            try:
                bars = daily_bars if timeframe == "1D" else load_bars(symbol, timeframe)
                values = adx(bars)
                start = "2024-01-01" if timeframe in ("1H", "4H") else "2022-01-01"
                for threshold in THRESHOLDS:
                    whole = backtest(bars, values, threshold, start, ticks[symbol])
                    late = backtest(bars, values, threshold, "2025-01-01", ticks[symbol])
                    rows.append({"symbol": symbol, "timeframe": timeframe,
                                 "adx_threshold": threshold, "bars": len(bars),
                                 "first_bar": bars[0]["ts"] if bars else "",
                                 "last_bar": bars[-1]["ts"] if bars else "",
                                 "median_daily_turnover_rub": median_turnover,
                                 **whole, **{f"late_{key}": value for key, value in late.items()}})
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": str(exc)})
    fields = list(rows[0])
    with (OUTPUT / "all_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUTPUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2))
    grouped = {}
    for row in rows:
        grouped.setdefault((row["symbol"], row["timeframe"]), {})[row["adx_threshold"]] = row
    for symbol in {row["symbol"] for row in rows}:
        ticker_rows = [grouped[(symbol, timeframe)] for timeframe in TIMEFRAMES
                       if (symbol, timeframe) in grouped]
        lines = [f"# {symbol} · EMA12/33 с ADX14", "",
                 "Локальное сравнение на свечах MOEX ISS; ADX фильтрует новый вход, обратное пересечение всегда закрывает открытую позицию. Порог 0 — чистая EMA12/33 без фильтра. Результаты не сверены с TradingView.", "",
                 "| Интервал | Порог | Доходность | Просадка | PF | Закрытых / прибыльных | Long / short | Поздняя доходность |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for variants in ticker_rows:
            for threshold in THRESHOLDS:
                r = variants[threshold]
                lines.append(f"| {r['timeframe']} | {threshold} | {r['return_pct']:+.2f}% | {r['max_drawdown_pct']:.2f}% | {r['profit_factor']} | {r['closed_trades']} / {r['winning_trades']} | {r['long_trades']} / {r['short_trades']} | {r['late_return_pct']:+.2f}% |")
        lines += ["", "[Полный CSV](../../../all_results.csv). Выбор лучшего порога по этой таблице будет подгонкой к известной истории; требуется отдельная будущая проверка."]
        path = TICKERS / symbol
        path.mkdir(parents=True, exist_ok=True)
        (path / "README.md").write_text("\n".join(lines) + "\n")
    TICKERS.mkdir(parents=True, exist_ok=True)
    report = ["# EMA12/33 + ADX14: сравнение всего сохранённого рынка", "",
              f"Проверено {len(grouped)} пар тикер/интервал, {len({key[0] for key in grouped})} тикеров; ошибок чтения данных: {len(errors)}. Исходные свечи — кэш MOEX ISS до 30.10.2026. 1D/1W/1M доступны для полного списка, 1H/4H — для 50 наиболее оборотных. Порог 0 — контроль без ADX.", "",
              "| Интервал | Порог | Пар с положительным итогом | Пар лучше контроля по доходности | Медиана изменения доходности, п.п. |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for timeframe in TIMEFRAMES:
        pairs = [v for (symbol, tf), v in grouped.items() if tf == timeframe]
        for threshold in (20, 25):
            usable = [v for v in pairs if v[0]["closed_trades"] >= 1]
            deltas = [v[threshold]["return_pct"] - v[0]["return_pct"] for v in usable]
            positives = sum(v[threshold]["return_pct"] > 0 for v in usable)
            improved = sum(d > 0 for d in deltas)
            median = statistics.median(deltas) if deltas else 0
            report.append(f"| {timeframe} | {threshold} | {positives}/{len(usable)} | {improved}/{len(usable)} | {median:+.2f} |")
    report += ["", "## Как читать", "",
               "ADX вычислен по Wilder RMA(14) для DI и ADX. Сигнал EMA оценивается на закрытой свече, сделка — на открытии следующей. Начальный капитал 1 млн ₽, доля 25%, комиссия 0,05% за сторону, проскальзывание 1 тик по MINSTEP MOEX. Открытая позиция включена в доходность и просадку, но не в число закрытых сделок. Short без платы за заём и дивидендных обязательств. Локальный расчёт может отличаться от TradingView по свечам и прогреву ADX.", "",
               "Это исследование на уже известных данных. Порог 20/25 выбран заранее, но выбор тикера по лучшему прошлому результату остаётся смещённым. Для решений используйте отдельную будущую проверку и сверку сделок в TradingView.", "",
               "[Все результаты](all_results.csv), [ошибки](errors.json), тикерные страницы в `research/tickers/<ТИКЕР>/README.md`."]
    (OUTPUT / "RESEARCH.md").write_text("\n".join(report) + "\n")
    selected = []
    for (symbol, timeframe), variants in grouped.items():
        baseline = variants[0]
        for threshold in (20, 25):
            current = variants[threshold]
            if (timeframe not in ("1D", "4H") or
                    current["median_daily_turnover_rub"] < 50_000_000 or
                    current["closed_trades"] < 10 or
                    current["late_closed_trades"] < 3 or
                    current["late_winning_trades"] < 1 or
                    current["return_pct"] <= 0 or
                    current["late_return_pct"] <= 0 or
                    current["return_pct"] <= baseline["return_pct"] or
                    current["late_return_pct"] <= baseline["late_return_pct"] or
                    current["max_drawdown_pct"] < baseline["max_drawdown_pct"] or
                    current["profit_factor"] <= 1):
                continue
            selected.append({"symbol": symbol, "timeframe": timeframe,
                             "adx_threshold": threshold,
                             "return_pct": current["return_pct"],
                             "baseline_return_pct": baseline["return_pct"],
                             "late_return_pct": current["late_return_pct"],
                             "baseline_late_return_pct": baseline["late_return_pct"],
                             "max_drawdown_pct": current["max_drawdown_pct"],
                             "baseline_max_drawdown_pct": baseline["max_drawdown_pct"],
                             "closed_trades": current["closed_trades"],
                             "winning_trades": current["winning_trades"],
                             "long_trades": current["long_trades"],
                             "short_trades": current["short_trades"],
                             "profit_factor": current["profit_factor"]})
    selected.sort(key=lambda r: (r["timeframe"] != "1D",
                                 -(r["late_return_pct"] - r["baseline_late_return_pct"])))
    SUCCESS.mkdir(parents=True, exist_ok=True)
    selected_symbols = {row["symbol"] for row in selected}
    for old_folder in SUCCESS.iterdir():
        if (old_folder.is_dir() and old_folder.name not in selected_symbols and
                {item.name for item in old_folder.iterdir()} == {"README.md"}):
            (old_folder / "README.md").unlink()
            old_folder.rmdir()
    with (SUCCESS / "selected.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(selected[0]) if selected else
                                ["symbol", "timeframe", "adx_threshold"])
        writer.writeheader()
        writer.writerows(selected)
    success_lines = ["# Исторические кандидаты EMA12/33 + ADX14", "",
                     "Критерии: медианный дневной оборот ≥50 млн ₽; ≥10 закрытых сделок за полный и ≥3 с 2025 года, хотя бы одна прибыльная поздняя; положительная доходность полного и позднего периода выше чистой EMA12/33; просадка не глубже контроля; profit factor >1. Порог 20 или 25. Отбор сделан **на уже известных данных** и не подтверждает будущую доходность. Short без реальной стоимости займа и дивидендных обязательств.", "",
                     "| Тикер | Интервал | ADX ≥ | Доходность ADX / контроль | Поздняя ADX / контроль | Просадка ADX / контроль | Сделок / прибыльных | PF |",
                     "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for symbol in selected_symbols:
        folder = SUCCESS / symbol
        folder.mkdir(exist_ok=True)
        page = folder / "README.md"
        lines = [f"# {symbol} · EMA12/33 + ADX14", "",
                 f"[Все интервалы](../../execute/research/tickers/{symbol}/README.md) · "
                 "[Pine для TradingView](../../execute/strategy.pine).", "",
                 "| Интервал | ADX ≥ | Фильтр / база | С 2025 года фильтр / база | Просадка фильтр / база | Сделок / прибыльных | PF |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in (item for item in selected if item["symbol"] == symbol):
            lines.append(f"| {row['timeframe']} | {row['adx_threshold']} | "
                         f"{row['return_pct']:+.2f}% / {row['baseline_return_pct']:+.2f}% | "
                         f"{row['late_return_pct']:+.2f}% / {row['baseline_late_return_pct']:+.2f}% | "
                         f"{row['max_drawdown_pct']:.2f}% / {row['baseline_max_drawdown_pct']:.2f}% | "
                         f"{row['closed_trades']} / {row['winning_trades']} | {row['profit_factor']} |")
        lines += ["", "Результат локального бэктеста MOEX ISS, выбран после просмотра рынка; сделки TradingView ещё не сверены."]
        page.write_text("\n".join(lines) + "\n")
    for row in selected:
        symbol = row["symbol"]
        success_lines.append(
            f"| [{symbol}]({symbol}/README.md) | {row['timeframe']} | {row['adx_threshold']} | "
            f"{row['return_pct']:+.2f}% / {row['baseline_return_pct']:+.2f}% | "
            f"{row['late_return_pct']:+.2f}% / {row['baseline_late_return_pct']:+.2f}% | "
            f"{row['max_drawdown_pct']:.2f}% / {row['baseline_max_drawdown_pct']:.2f}% | "
            f"{row['closed_trades']} / {row['winning_trades']} | {row['profit_factor']} |")
    success_lines += ["", "[Все отобранные строки](selected.csv), [полная таблица без отбора](../execute/all_results.csv).", "",
                      "1W и 1M не попали в этот список из-за малого числа сделок на доступной истории; их результаты есть в полной таблице. Наличие бумаги в этом списке не является рекомендацией к торговле."]
    (SUCCESS / "README.md").write_text("\n".join(success_lines) + "\n")
    print(f"rows={len(rows)} groups={len(grouped)} errors={len(errors)}")


if __name__ == "__main__":
    main()
