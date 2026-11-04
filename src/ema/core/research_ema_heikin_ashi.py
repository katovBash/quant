"""EMA12/33 HA signals: compare real fills with misleading synthetic HA fills."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.ema.core.adx_ema import SCAN, TIMEFRAMES, load_bars
from src.ema.core.research_ema_combinations import crosses, simulate

ROOT = Path("experiments/.history/legacy-ema/12-33-cross/execute/variants/long-short/execute/variants/heikin-ashi-signal")
OUT = ROOT / "execute"


def heikin_ashi(bars: list[dict]) -> list[dict]:
    result = []
    prior_open = prior_close = None
    for bar in bars:
        ha_close = (bar["open"] + bar["high"] + bar["low"] + bar["close"]) / 4
        ha_open = ((bar["open"] + bar["close"]) / 2 if prior_open is None
                   else (prior_open + prior_close) / 2)
        result.append({"ts": bar["ts"], "open": ha_open,
                       "high": max(bar["high"], ha_open, ha_close),
                       "low": min(bar["low"], ha_open, ha_close),
                       "close": ha_close, "volume": bar["volume"]})
        prior_open, prior_close = ha_open, ha_close
    return result


def win_rate(row: dict, prefix: str) -> float:
    count = int(row[prefix + "closed_trades"])
    return 100 * int(row[prefix + "winning_trades"]) / count if count else 0.0


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    universe = json.loads((SCAN / "daily_weekly_monthly/universe.json").read_text())
    liquid = {entry["SECID"] for entry in json.loads((SCAN / "intraday/universe.json").read_text())}
    rows, errors = [], []
    for entry in universe:
        symbol = entry["SECID"]
        tick = float(entry.get("MINSTEP") or 0)
        try:
            daily = load_bars(symbol, "1D")
            train_daily = [bar for bar in daily if bar["ts"][:10] < "2025-01-01"]
            turnover = statistics.median(bar["close"] * bar["volume"] for bar in train_daily) if train_daily else 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"symbol": symbol, "timeframe": "1D", "error": str(exc)})
            continue
        for timeframe in TIMEFRAMES:
            if timeframe in ("1H", "4H") and symbol not in liquid:
                continue
            try:
                bars = daily if timeframe == "1D" else load_bars(symbol, timeframe)
                ha = heikin_ashi(bars)
                normal_signals = crosses(bars)
                ha_signals = crosses(ha)
                allowed = [True] * len(bars)
                start = "2024-01-01" if timeframe in ("1H", "4H") else "2022-01-01"
                row = {"symbol": symbol, "timeframe": timeframe, "bars": len(bars),
                       "first_bar": bars[0]["ts"] if bars else "",
                       "last_bar": bars[-1]["ts"] if bars else "",
                       "train_daily_turnover_rub": round(turnover, 2)}
                for period, period_start, end in (("train", start, "2025-01-01"),
                                                   ("late", "2025-01-01", None),
                                                   ("full", start, None)):
                    for name, execution_bars, signals in (("base", bars, normal_signals),
                                                          ("ha_real", bars, ha_signals),
                                                          ("ha_synthetic", ha, ha_signals)):
                        metrics = simulate(execution_bars, signals, allowed, allowed, tick, period_start, end)
                        row.update({f"{period}_{name}_{key}": value for key, value in metrics.items()})
                rows.append(row)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append({"symbol": symbol, "timeframe": timeframe, "error": str(exc)})
    with (OUT / "all_results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2))
    by_symbol = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(row)
    tickers = ROOT / "tickers"
    tickers.mkdir(parents=True, exist_ok=True)
    (tickers / "README.md").write_text(f"# Тикеры HA-сигнала\n\n{len(by_symbol)} символов. Для каждого есть таблица `<ТИКЕР>/README.md`; [полный CSV](../execute/all_results.csv).\n")
    for symbol, symbol_rows in by_symbol.items():
        page = [f"# {symbol} · EMA12/33 на Heikin Ashi", "",
                "**HA real** — сигнал по HA, исполнение и оценка по обычным свечам. **HA synthetic** моделирует заполнение по ненастоящим ценам HA; служит только диагностикой расхождения с экраном TradingView.", "",
                "| Интервал | Поздняя база | Поздняя HA real | Поздняя HA synthetic | HA real сделки / прибыльные | Win rate | PF | Просадка |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for row in symbol_rows:
            page.append(f"| {row['timeframe']} | {float(row['late_base_return_pct']):+.2f}% | {float(row['late_ha_real_return_pct']):+.2f}% | {float(row['late_ha_synthetic_return_pct']):+.2f}% | {row['late_ha_real_closed_trades']} / {row['late_ha_real_winning_trades']} | {win_rate(row, 'late_ha_real_'):.1f}% | {row['late_ha_real_profit_factor']} | {float(row['late_ha_real_max_drawdown_pct']):.2f}% |")
        page += ["", "[Полные ранние, поздние и общие метрики](../../execute/all_results.csv). Локальный расчёт нужно сверить со сделками Pine."]
        folder = tickers / symbol
        folder.mkdir(exist_ok=True)
        (folder / "README.md").write_text("\n".join(page) + "\n")
    report = ["# EMA12/33 на Heikin Ashi: честная проверка исполнения", "",
              f"{len(rows)} пар символ/интервал, {len(by_symbol)} символов, {len(errors)} ошибок. HA-сигнал вычислен из OHLC каждого интервала; сделки в основной колонке HA real моделируются на следующем **обычном** открытии MOEX. HA synthetic — диагностический тест синтетических цен, не результат для торговли. История до 2025 и с 2025 года отдельно.", "",
              "| Интервал | HA real лучше базы по поздней доходности | HA synthetic лучше HA real | Медиана изменения HA real − база, п.п. | Медиана закрытых сделок HA real |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for timeframe in TIMEFRAMES:
        eligible = [r for r in rows if r["timeframe"] == timeframe and int(r["late_base_closed_trades"]) >= 1]
        deltas = [float(r["late_ha_real_return_pct"]) - float(r["late_base_return_pct"]) for r in eligible]
        synthetic_deltas = [float(r["late_ha_synthetic_return_pct"]) - float(r["late_ha_real_return_pct"]) for r in eligible]
        report.append(f"| {timeframe} | {sum(d > 0 for d in deltas)}/{len(eligible)} | {sum(d > 0 for d in synthetic_deltas)}/{len(eligible)} | {statistics.median(deltas) if deltas else 0:+.2f} | {statistics.median(int(r['late_ha_real_closed_trades']) for r in eligible) if eligible else 0:.1f} |")
    report += ["", "Исполнение по синтетическим HA OHLC может искусственно улучшать или ухудшать отчёт: эти цены нельзя получить в обычной заявке. На Heikin Ashi графике TradingView включите `Using standard OHLC` / `Standard bars`, либо используйте наш Pine на обычном свечном графике с запросом HA-сигнала. Иначе нельзя напрямую сравнивать проценты.", "",
               "Начальный капитал 1 млн ₽, 25% на вход, комиссия 0,05% за сторону, проскальзывание 1 тик. Short без платы за заём и дивидендных обязательств. Выбор бумаги по этим данным смещён; требуется новый бумажный период.", "",
               "[Все результаты](all_results.csv) · [исторический отбор](../success/README.md) · [ошибки](errors.json)."]
    (OUT / "RESEARCH.md").write_text("\n".join(report) + "\n")
    selected = []
    for row in rows:
        if row["timeframe"] not in ("1D", "4H") or float(row["train_daily_turnover_rub"]) < 50_000_000:
            continue
        minimum_train = 5 if row["timeframe"] == "1D" else 10
        minimum_late = 3 if row["timeframe"] == "1D" else 8
        if (int(row["train_ha_real_closed_trades"]) < minimum_train or
                int(row["late_ha_real_closed_trades"]) < minimum_late or
                int(row["late_ha_real_winning_trades"]) < 1 or
                float(row["train_ha_real_return_pct"]) <= max(0, float(row["train_base_return_pct"])) or
                float(row["late_ha_real_return_pct"]) <= max(0, float(row["late_base_return_pct"])) or
                float(row["late_ha_real_max_drawdown_pct"]) < float(row["late_base_max_drawdown_pct"]) - 2 or
                float(row["late_ha_real_profit_factor"]) <= 1):
            continue
        selected.append(row)
    selected.sort(key=lambda r: (r["timeframe"] != "1D", -(float(r["late_ha_real_return_pct"]) - float(r["late_base_return_pct"]))))
    success = ROOT / "success"
    success.mkdir(parents=True, exist_ok=True)
    with (success / "selected.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(selected)
    lines = ["# Исторические кандидаты HA-сигнала с реальным исполнением", "",
             f"Найдено {len(selected)} строк: положительная доходность выше обычной EMA12/33 до и после 01.01.2025, достаточный оборот и число сделок, поздний PF >1, просадка не хуже базы более чем на 2 п.п. Синтетическое исполнение **не** участвует в отборе.", "",
             "| Символ | Интервал | Поздняя база → HA real | Сделки / прибыльные | Win rate | PF | Просадка |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in selected[:40]:
        lines.append(f"| [{row['symbol']}](../tickers/{row['symbol']}/README.md) | {row['timeframe']} | {float(row['late_base_return_pct']):+.2f}% → {float(row['late_ha_real_return_pct']):+.2f}% | {row['late_ha_real_closed_trades']} / {row['late_ha_real_winning_trades']} | {win_rate(row, 'late_ha_real_'):.1f}% | {row['late_ha_real_profit_factor']} | {float(row['late_ha_real_max_drawdown_pct']):.2f}% |")
    lines += ["", "[Все отобранные строки](selected.csv) · [полная таблица](../execute/all_results.csv). Исторический отбор не является прогнозом."]
    (success / "README.md").write_text("\n".join(lines) + "\n")
    print(f"heikin ashi: rows={len(rows)}, selected={len(selected)}, errors={len(errors)}")


if __name__ == "__main__":
    main()
