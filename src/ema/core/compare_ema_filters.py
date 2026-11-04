"""Compare separate RSI and confirmed-pivot trendline filters with EMA12/33."""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from pathlib import Path

from src.ema.core.adx_ema import CACHE, SCAN, TIMEFRAMES, backtest, load_bars, rma

BASE = Path("experiments/.history/legacy-ema/12-33-cross/execute/variants/long-short/execute/variants")
KINDS = ("rsi-filter", "trendline-filter", "channel-zone-filter", "regression-channel")
LOOKBACK = {"1D": 252, "1W": 52, "1M": 12, "1H": 500, "4H": 252}


def rsi(bars: list[dict], length: int = 14) -> list[float]:
    gains, losses = [math.nan], [math.nan]
    for previous, current in zip(bars, bars[1:]):
        change = current["close"] - previous["close"]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    average_gains, average_losses = rma(gains, length), rma(losses, length)
    values = []
    for gain, loss in zip(average_gains, average_losses):
        if not math.isfinite(gain) or not math.isfinite(loss):
            values.append(math.nan)
        elif loss == 0:
            values.append(100.0 if gain else 50.0)
        else:
            values.append(100.0 - 100.0 / (1.0 + gain / loss))
    return values


def trendlines(bars: list[dict], wing: int = 3) -> list[tuple[float, float]]:
    """At bar i, use only pivots whose right wing has closed by i."""
    high_pivots: list[tuple[int, float]] = []
    low_pivots: list[tuple[int, float]] = []
    result = []
    for i in range(len(bars)):
        pivot = i - wing
        if pivot >= wing:
            window = bars[pivot - wing:pivot + wing + 1]
            high = bars[pivot]["high"]
            low = bars[pivot]["low"]
            if high > max(bar["high"] for bar in window[:wing]) and high >= max(bar["high"] for bar in window[wing + 1:]):
                high_pivots.append((pivot, high))
            if low < min(bar["low"] for bar in window[:wing]) and low <= min(bar["low"] for bar in window[wing + 1:]):
                low_pivots.append((pivot, low))

        def project(points: list[tuple[int, float]]) -> float:
            if len(points) < 2:
                return math.nan
            (x1, y1), (x2, y2) = points[-2:]
            return y2 + (y2 - y1) * (i - x2) / (x2 - x1)

        result.append((project(high_pivots), project(low_pivots)))
    return result


def regression_channel(bars: list[dict], length: int) -> list[tuple[float, float]]:
    """Past-only linear fit of closes with two residual-standard-deviation bands."""
    closes = [bar["close"] for bar in bars]
    result = [(math.nan, math.nan)] * len(bars)
    if len(bars) <= length:
        return result
    sx = length * (length - 1) / 2
    sxx = length * (length - 1) * (2 * length - 1) / 6 - sx * sx / length
    window = closes[:length]
    sy = sum(window)
    syy = sum(value * value for value in window)
    sxy = sum(index * value for index, value in enumerate(window))
    for i in range(length, len(bars)):
        covariance = sxy - sx * sy / length
        slope = covariance / sxx
        mean = sy / length
        predicted = mean + slope * (length - (length - 1) / 2)
        residual_variance = max(0.0, (syy - sy * sy / length - slope * covariance) / length)
        band = 2 * math.sqrt(residual_variance)
        result[i] = (predicted + band, predicted - band)
        old, new = closes[i - length], closes[i]
        sxy = sxy - (sy - old) + (length - 1) * new
        sy += new - old
        syy += new * new - old * old
    return result


def filter_for(kind: str, bars: list[dict], timeframe: str = "1D"):
    if kind == "rsi-filter":
        values = rsi(bars)
        return lambda i, side: math.isfinite(values[i]) and (values[i] > 50 if side > 0 else values[i] < 50)
    if kind == "regression-channel":
        values = regression_channel(bars, LOOKBACK[timeframe])
        def has_room(i: int, side: int) -> bool:
            upper, lower = values[i]
            close = bars[i]["close"]
            if not (math.isfinite(upper) and math.isfinite(lower)):
                return False
            width = upper - lower
            if width <= 0 or close <= 0 or width / close < 0.03:
                return False
            position = (close - lower) / width
            return 0 <= position <= 0.65 if side > 0 else 0.35 <= position <= 1
        return has_room
    values = trendlines(bars)
    if kind == "channel-zone-filter":
        def near_wall(i: int, side: int) -> bool:
            resistance, support = values[i]
            close = bars[i]["close"]
            if not (math.isfinite(resistance) and math.isfinite(support)):
                return False
            width = resistance - support
            if width <= 0 or close <= 0 or width / close < 0.03:
                return False
            location = (close - support) / width
            return 0 <= location <= 0.35 if side > 0 else 0.65 <= location <= 1
        return near_wall
    return lambda i, side: (math.isfinite(values[i][0]) and bars[i]["close"] > values[i][0]
                            if side > 0 else math.isfinite(values[i][1]) and bars[i]["close"] < values[i][1])


def main(kind: str) -> None:
    if kind not in KINDS:
        raise ValueError(f"Choose one of {KINDS}")
    root = BASE / kind
    output, tickers, success = root / "execute", root / "tickers", root / "success"
    for folder in (output, tickers, success):
        folder.mkdir(parents=True, exist_ok=True)
    universe = json.loads((SCAN / "daily_weekly_monthly/universe.json").read_text())
    intraday = json.loads((SCAN / "intraday/universe.json").read_text())
    liquid = {item["SECID"] for item in intraday}
    rows, errors = [], []
    label = {"rsi-filter": "RSI14 >50 long / <50 short",
             "trendline-filter": "confirmed pivot trendline breakout (3/3)",
             "channel-zone-filter": "confirmed pivot support/resistance zones (3/3)",
             "regression-channel": "past-only regression channel ±2 residual sigma"}[kind]
    for entry in universe:
        symbol = entry["SECID"]
        tick = float(entry.get("MINSTEP") or 0)
        try:
            daily = load_bars(symbol, "1D")
            turnover = statistics.median(bar["volume"] * bar["close"] for bar in daily) if daily else 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"symbol": symbol, "timeframe": "1D", "error": str(exc)})
            continue
        for timeframe in TIMEFRAMES:
            if timeframe in ("1H", "4H") and symbol not in liquid:
                continue
            try:
                bars = daily if timeframe == "1D" else load_bars(symbol, timeframe)
                gate = filter_for(kind, bars, timeframe)
                start = "2024-01-01" if timeframe in ("1H", "4H") else "2022-01-01"
                baseline = backtest(bars, [], 0, start, tick)
                filtered = backtest(bars, [], 0, start, tick, entry_filter=gate)
                late_base = backtest(bars, [], 0, "2025-01-01", tick)
                late_filter = backtest(bars, [], 0, "2025-01-01", tick, entry_filter=gate)
                row = {"symbol": symbol, "timeframe": timeframe, "bars": len(bars),
                       "first_bar": bars[0]["ts"] if bars else "", "last_bar": bars[-1]["ts"] if bars else "",
                       "median_daily_turnover_rub": round(turnover, 2)}
                for prefix, result in (("base_", baseline), ("filter_", filtered),
                                       ("late_base_", late_base), ("late_filter_", late_filter)):
                    row.update({prefix + key: value for key, value in result.items()})
                rows.append(row)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": str(exc)})
    with (output / "all_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2))

    by_symbol: dict[str, list[dict]] = {}
    for row in rows:
        by_symbol.setdefault(row["symbol"], []).append(row)
    for symbol, ticker_rows in by_symbol.items():
        lines = [f"# {symbol} · EMA12/33 + {label}", "",
                 "Локальный тест MOEX ISS. Встречное пересечение всегда закрывает позицию; фильтр решает только вопрос нового входа.", "",
                 "| Интервал | База | С фильтром | Разница, п.п. | Просадка база / фильтр | Сделки / прибыльные база → фильтр | Поздний период база / фильтр |",
                 "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in ticker_rows:
            delta = row["filter_return_pct"] - row["base_return_pct"]
            lines.append(f"| {row['timeframe']} | {row['base_return_pct']:+.2f}% | {row['filter_return_pct']:+.2f}% | {delta:+.2f} | {row['base_max_drawdown_pct']:.2f}% / {row['filter_max_drawdown_pct']:.2f}% | {row['base_closed_trades']}/{row['base_winning_trades']} → {row['filter_closed_trades']}/{row['filter_winning_trades']} | {row['late_base_return_pct']:+.2f}% / {row['late_filter_return_pct']:+.2f}% |")
        lines += ["", "[Полный CSV](../../execute/all_results.csv). Выбор по прошлой доходности требует независимой будущей проверки."]
        folder = tickers / symbol
        folder.mkdir(exist_ok=True)
        (folder / "README.md").write_text("\n".join(lines) + "\n")

    usable = [row for row in rows if row["base_closed_trades"] >= 1]
    report = [f"# EMA12/33 + {label}: весь сохранённый рынок", "",
              f"{len(by_symbol)} символов, {len(rows)} пар символ/интервал, {len(errors)} ошибок. Кэш MOEX ISS до 30.10.2026: 1D/1W/1M для всех, 1H/4H для 50 более оборотных. Контроль — тот же симулятор с чистой EMA12/33.", "",
              "| Интервал | Положительный итог фильтра | Лучше контроля | Медиана изменения, п.п. | Медиана числа закрытых сделок |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for timeframe in TIMEFRAMES:
        subset = [row for row in usable if row["timeframe"] == timeframe]
        deltas = [row["filter_return_pct"] - row["base_return_pct"] for row in subset]
        report.append(f"| {timeframe} | {sum(row['filter_return_pct'] > 0 for row in subset)}/{len(subset)} | {sum(delta > 0 for delta in deltas)}/{len(subset)} | {statistics.median(deltas) if deltas else 0:+.2f} | {statistics.median(row['filter_closed_trades'] for row in subset) if subset else 0:.1f} |")
    report += ["", "Начальный капитал 1 млн ₽, размер 25% капитала, комиссия 0,05% за сторону, проскальзывание 1 тик, сигнал по закрытой свече и исполнение на следующем открытии. Открытая позиция включена в доходность, но не в число закрытых сделок. Short не учитывает заём и дивидендные обязательства. Кэш и агрегация 4H могут отличаться от TradingView.", "",
               "Показатель «лучше контроля» относится к известной истории; многократный перебор тикеров и фильтров завышает ожидаемую будущую доходность. Страницы каждого символа лежат в `../tickers/<ТИКЕР>/README.md`."]
    (output / "RESEARCH.md").write_text("\n".join(report) + "\n")
    selected = [row for row in rows if row["timeframe"] in ("1D", "4H")
                and row["median_daily_turnover_rub"] >= 50_000_000
                and row["filter_closed_trades"] >= 10 and row["late_filter_closed_trades"] >= 3
                and row["late_filter_winning_trades"] >= 1
                and row["filter_return_pct"] > max(0, row["base_return_pct"])
                and row["late_filter_return_pct"] > max(0, row["late_base_return_pct"])
                and row["filter_max_drawdown_pct"] >= row["base_max_drawdown_pct"]
                and row["filter_profit_factor"] != "inf" and row["filter_profit_factor"] > 1]
    selected.sort(key=lambda row: (row["timeframe"] != "1D", -(row["late_filter_return_pct"] - row["late_base_return_pct"])))
    with (success / "selected.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    lines = [f"# Исторические кандидаты EMA12/33 + {label}", "",
             "Критерии: 1D/4H, исторический медианный дневной оборот ≥50 млн ₽, минимум 10 закрытых сделок и 3 с 2025 года (минимум одна прибыльная), положительная доходность выше чистой EMA в обоих периодах, просадка не глубже контроля, PF >1. Это **отбор по уже известным данным**, не сигнал к реальной сделке.", "",
             "| Символ | Интервал | База → фильтр | Поздний период база → фильтр | Сделок / прибыльных | Просадка | PF |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in selected:
        symbol = row["symbol"]
        lines.append(f"| [{symbol}]({symbol}/README.md) | {row['timeframe']} | {row['base_return_pct']:+.2f}% → {row['filter_return_pct']:+.2f}% | {row['late_base_return_pct']:+.2f}% → {row['late_filter_return_pct']:+.2f}% | {row['filter_closed_trades']} / {row['filter_winning_trades']} | {row['filter_max_drawdown_pct']:.2f}% | {row['filter_profit_factor']} |")
    if not selected:
        lines += ["", "Ни одна пара символ/интервал не прошла эти критерии. Пока нет кандидатов для paper trading по этому варианту."]
    for symbol in {row["symbol"] for row in selected}:
        ticker_rows = [row for row in selected if row["symbol"] == symbol]
        page = [f"# {symbol} · {label}", "", "Исторические строки, прошедшие формальные критерии:", "",
                "| Интервал | База | Фильтр | Поздняя база | Поздний фильтр | Закрытых / прибыльных |",
                "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for row in ticker_rows:
            page.append(f"| {row['timeframe']} | {row['base_return_pct']:+.2f}% | {row['filter_return_pct']:+.2f}% | {row['late_base_return_pct']:+.2f}% | {row['late_filter_return_pct']:+.2f}% | {row['filter_closed_trades']} / {row['filter_winning_trades']} |")
        page += ["", f"[Pine](../../execute/strategy.pine) · [все интервалы](../../tickers/{symbol}/README.md).", "", "Локальный результат MOEX ISS; сделки Pine в TradingView ещё не сверены."]
        folder = success / symbol
        folder.mkdir(exist_ok=True)
        (folder / "README.md").write_text("\n".join(page) + "\n")
    lines += ["", "[CSV отобранных](selected.csv) · [весь скан](../execute/all_results.csv)."]
    (success / "README.md").write_text("\n".join(lines) + "\n")
    (tickers / "README.md").write_text(f"# Тикеры EMA12/33 + {label}\n\nДля каждого из {len(by_symbol)} сохранённых символов: `<ТИКЕР>/README.md`; данные по 1D/1W/1M и, где доступны, 1H/4H. [Полный CSV](../execute/all_results.csv).\n")
    print(f"{kind}: rows={len(rows)}, symbols={len(by_symbol)}, selected={len(selected)}, errors={len(errors)}")


if __name__ == "__main__":
    main(sys.argv[1])
