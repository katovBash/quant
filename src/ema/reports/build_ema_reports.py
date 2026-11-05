"""Build per-ticker Markdown evidence from scan_ema.py CSV files."""

from __future__ import annotations

import csv
import html
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from src.ema.core.scan_ema import ema

ROOT = Path("experiments/.history/legacy-ema/12-33-cross")
DAILY = ROOT / "execute/research/daily_weekly_monthly"
INTRADAY = ROOT / "execute/research/intraday"
SUCCESS = ROOT / "success"
TICKERS = ROOT / "execute/research/tickers"
CACHE = Path("data/candles/moex_scan")


def read_csv(path):
    return list(csv.DictReader(path.open(encoding="utf-8"))) if path.exists() else []


def num(row, key):
    try:
        return float(row[key])
    except (ValueError, TypeError, KeyError):
        return 0.0


def daily_bars(symbol):
    paths = sorted(CACHE.glob(f"{symbol}_24_2022-01-01_2026-10-30.json"))
    return json.loads(paths[0].read_text()) if paths else []


def svg_chart(symbol, bars, path):
    if len(bars) < 34:
        return False
    full_price = [b["close"] for b in bars]
    e12 = ema(full_price, 12)[-260:]
    e33 = ema(full_price, 33)[-260:]
    bars = bars[-260:]
    price = full_price[-260:]
    low = min(price + e12 + e33)
    high = max(price + e12 + e33)
    span = max(high - low, 1e-9)
    width, height = 1000, 420
    def points(values):
        return " ".join(f"{40+i*920/(len(values)-1):.1f},{350-(v-low)*290/span:.1f}"
                        for i, v in enumerate(values))
    title = html.escape(symbol)
    label = f"MOEX ISS TQBR, 1D, {bars[0]['ts'][:10]} — {bars[-1]['ts'][:10]}"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#101827"/>
<text x="40" y="34" fill="white" font-family="Arial" font-size="22">{title} · EMA 12/33</text>
<text x="40" y="396" fill="#aebbd0" font-family="Arial" font-size="15">{html.escape(label)} · chart generated from exchange candles</text>
<line x1="40" y1="350" x2="960" y2="350" stroke="#344156"/>
<polyline points="{points(price)}" fill="none" stroke="#f5f7fb" stroke-width="1.5" opacity=".72"/>
<polyline points="{points(e12)}" fill="none" stroke="#24d3e8" stroke-width="2"/>
<polyline points="{points(e33)}" fill="none" stroke="#ffac32" stroke-width="2"/>
<text x="760" y="34" fill="#f5f7fb" font-family="Arial" font-size="14">Цена</text>
<text x="820" y="34" fill="#24d3e8" font-family="Arial" font-size="14">EMA12</text>
<text x="900" y="34" fill="#ffac32" font-family="Arial" font-size="14">EMA33</text>
</svg>'''
    path.write_text(svg, encoding="utf-8")
    return True


def qualify(row, median_turnover):
    return (row["status"] == "candidate" and median_turnover >= 50_000_000
            and num(row, "excess_return_pp") > 0 and num(row, "oos_excess_pp") > 0
            and num(row, "oos_winning_trades") >= 1)


def line(row):
    return (f"| {row['timeframe']} | {row['mode']} | {row['fast']}/{row['slow']} | "
            f"{row['closed_trades']} | {row['winning_trades']}/{row['closed_trades']} ({row['win_rate_pct'] or '—'}%) | "
            f"{row['net_return_pct']}% | {row['max_drawdown_pct']}% | "
            f"{row['oos_trades']} | {row['oos_return_pct']}% | "
            f"{row['oos_excess_pp']} п.п. |")


def main():
    day_rows = read_csv(DAILY / "all_results.csv")
    hour_rows = read_csv(INTRADAY / "all_results.csv")
    rows = day_rows + hour_rows
    if not day_rows or "mode" not in day_rows[0]:
        raise RuntimeError("daily scan must be rerun with long/short/both modes")
    if hour_rows and "mode" not in hour_rows[0]:
        raise RuntimeError("intraday scan must be rerun with long/short/both modes")
    universe = {x["SECID"]: x for x in json.loads((DAILY / "universe.json").read_text())}
    by_symbol = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(row)
    median_turnover = {}
    for symbol in by_symbol:
        bars = daily_bars(symbol)
        median_turnover[symbol] = statistics.median(
            [b["close"] * b["volume"] for b in bars[-60:]]) if bars else 0
    SUCCESS.mkdir(parents=True, exist_ok=True)
    TICKERS.mkdir(parents=True, exist_ok=True)
    candidates = []
    for symbol in sorted(by_symbol):
        symbol_rows = by_symbol[symbol]
        base = [r for r in symbol_rows if r["fast"] == "12" and r["slow"] == "33"]
        base.sort(key=lambda r: ({"1D": 0, "1W": 1, "1M": 2, "1H": 3, "4H": 4}.get(r["timeframe"], 9),
                                 {"long": 0, "short": 1, "long_short": 2}.get(r["mode"], 9)))
        selected = [r for r in base if qualify(r, median_turnover[symbol])]
        candidates.extend(selected)
        path = TICKERS / symbol
        path.mkdir(parents=True, exist_ok=True)
        info = universe.get(symbol, {})
        lines = [f"# {symbol} — {info.get('SHORTNAME', '')}", "",
                 "Источники: MOEX ISS TQBR; расчёт `scan_ema.py`. Цена и свечи биржевые; это не отчёт TradingView.",
                 f"Медианный оборот последних 60 дневных баров: **{median_turnover[symbol]/1e6:.1f} млн ₽**.",
                 "", "## EMA 12/33 по режимам", "",
                 "| Интервал | Режим | EMA | Закрытых сделок | Прибыльных | Доходность | Макс. просадка | Сделок 2025–26 | Доходность 2025–26 | Превышение удержания 2025–26 |",
                 "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        lines += [line(r) for r in base]
        lines += ["", "`long` — только покупки; `short` — только короткие позиции; `long_short` — переворот на каждом пересечении. Выход — следующее обратное пересечение. Открытая позиция не входит в число закрытых сделок.", ""]
        valid_alts = [r for r in symbol_rows if not (r["fast"] == "12" and r["slow"] == "33")
                      and r["status"] == "candidate" and r["timeframe"] == "1D"]
        valid_alts.sort(key=lambda r: num(r, "oos_return_pct"), reverse=True)
        lines += ["## Другие пары EMA: лучшие результаты 1D", "",
                  "Это поиск по многим комбинациям; результат может быть случайным. Все строки, включая неудачные, находятся в общих CSV.", "",
                  "| Интервал | Режим | EMA | Закрытых сделок | Прибыльных | Доходность | Макс. просадка | Сделок 2025–26 | Доходность 2025–26 | Превышение удержания 2025–26 |",
                  "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        lines += [line(r) for r in valid_alts[:5]] or ["| — | — | — | — | — | — | — | — | — | — |"]
        if symbol == "LKOH":
            lines += ["", "## Присланный скриншот TradingView", "",
                      "![TradingView LKOH 1D](../../../evidence/LKOH_tradingview_2026-10-31.png)", "",
                      "На скриншоте период 1997–2026: +265,04% общей прибыли, 41/105 прибыльных сделок (39,05%), profit factor 2,263, просадка 17,87%. Название скрипта `VTBR`, хотя график `LKOH`; точное соответствие кода и настроек скриншотом не подтверждается."]
        lines += ["", "## Воспроизведение", "",
                  f"[Все результаты 1D/1W/1M](../../daily_weekly_monthly/all_results.csv) · [Все результаты 1H/4H](../../intraday/all_results.csv) · [TradingView: {symbol}](https://www.tradingview.com/symbols/RUS-{symbol}/)", ""]
        (path / "README.md").write_text("\n".join(lines), encoding="utf-8")
        if selected or symbol == "LKOH":
            dest = SUCCESS / symbol
            dest.mkdir(parents=True, exist_ok=True)
            bars = daily_bars(symbol)
            chart = svg_chart(symbol, bars, dest / "ema_12_33_daily.svg")
            selected_lines = [f"# {symbol} — EMA 12/33", "",
                              f"[Полный README тикера](../../execute/research/tickers/{symbol}/README.md) · [TradingView](https://www.tradingview.com/symbols/RUS-{symbol}/)", "",
                              f"Медианный оборот: **{median_turnover[symbol]/1e6:.1f} млн ₽**. Источник цифр ниже: **MOEX ISS + локальный расчёт**, не TradingView.", ""]
            if selected:
                selected_lines += ["Критерии: ≥10 закрытых сделок за полный период, ≥3 в 2025–2026 и ≥1 прибыльная поздняя сделка, положительная доходность и превышение удержания на обоих периодах, profit factor >1, просадка не глубже 30%, медианный оборот ≥50 млн ₽.", "",
                                   "| Интервал | Режим | EMA | Закрытых сделок | Прибыльных | Доходность | Макс. просадка | Сделок 2025–26 | Доходность 2025–26 | Превышение удержания 2025–26 |",
                                   "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
                selected_lines += [line(r) for r in selected]
                if any(r["mode"] != "long" for r in selected):
                    selected_lines += ["", "Результаты `short` и `long_short` оптимистичны: плата за заём, дивидендные обязательства и доступность шорта не учтены."]
            else:
                selected_lines += ["**Не прошёл отбор на периоде 2025–2026.** Папка сохранена из-за присланного скриншота TradingView."]
            if chart:
                selected_lines += ["", "![График MOEX EMA12/33](ema_12_33_daily.svg)", "",
                                   "График построен из свечей MOEX, это не скриншот TradingView."]
            if symbol == "LKOH":
                selected_lines += ["", "[Присланный скриншот TradingView](../../execute/evidence/LKOH_tradingview_2026-10-31.png): 39,05% прибыльных сделок, +265,04% за 1997–2026. Период и источник отличаются от локального теста."]
            (dest / "README.md").write_text("\n".join(selected_lines) + "\n", encoding="utf-8")
    candidates.sort(key=lambda r: (r["mode"], -num(r, "oos_return_pct")))
    with (SUCCESS / "candidates.csv").open("w", newline="", encoding="utf-8") as file:
        fields = ["symbol", "timeframe", "mode", "fast", "slow", "closed_trades",
                  "winning_trades",
                  "win_rate_pct", "net_return_pct", "profit_factor", "max_drawdown_pct",
                  "oos_trades", "oos_winning_trades", "oos_win_rate_pct", "oos_return_pct", "oos_excess_pp"]
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidates)
    counts = Counter(r["mode"] for r in candidates)
    summary = ["# EMA 12/33 — кандидаты по рынку РФ", "",
               "По состоянию на 31.10.2026: 505 активных инструментов TQBR на 1D/1W/1M; 1H/4H проверены для 50 наиболее оборотных. Все 45 пар из периодов 6, 12, 33, 66, 111, 222, 333, 444, 555, 666 проверены в режимах long, short, long+short. Это общий архив скана, а не результат только фиксированного EMA12/33 long-only Pine: сверяйте пару, направление и таймфрейм.", "",
               "`success` означает прохождение **заданного фильтра в историческом тесте**, не гарантию будущего дохода. Для short не учтены заём бумаги, дивидендные выплаты по короткой позиции и доступность шорта у брокера. 4H построен из последовательных часовых свечей MOEX и может отличаться от 4H TradingView.", "",
               f"Строк по режимам: long {counts['long']}, short {counts['short']}, long+short {counts['long_short']}. Полный перечень: [candidates.csv](candidates.csv).", "",
               "| Тикер | Интервал | Режим | Закрытых сделок | Прибыльных | Доходность | Просадка | Доходность 2025–26 |",
               "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in candidates[:60]:
        summary.append(f"| [{row['symbol']}]({row['symbol']}/README.md) | {row['timeframe']} | {row['mode']} | {row['closed_trades']} | {row['winning_trades']}/{row['closed_trades']} ({row['win_rate_pct']}%) | {row['net_return_pct']}% | {row['max_drawdown_pct']}% | {row['oos_return_pct']}% |")
    high_win = [r for r in candidates if num(r, "win_rate_pct") >= 50]
    summary += ["", "## Отдельно: ≥50% прибыльных закрытых сделок", "",
                "Этот показатель не является главным критерием прибыльности; он показывает частоту выигрышных сделок. Полная таблица содержит и стратегии с win rate ниже 50%, но положительным итогом.", "",
                "| Тикер | Интервал | Режим | Прибыльных / всего | Доходность |",
                "| --- | --- | --- | ---: | ---: |"]
    for row in high_win:
        summary.append(f"| [{row['symbol']}]({row['symbol']}/README.md) | {row['timeframe']} | {row['mode']} | {row['winning_trades']}/{row['closed_trades']} ({row['win_rate_pct']}%) | {row['net_return_pct']}% |")
    summary += ["", "## Источники и полные данные", "",
                "- [Все тикеры с отдельным README](../execute/research/tickers/)",
                "- [Все проверки 1D/1W/1M](../execute/research/daily_weekly_monthly/all_results.csv)",
                "- [Все проверки 1H/4H](../execute/research/intraday/all_results.csv)",
                "- [Сравнение 45 пар EMA](../execute/research/PAIR_COMPARISON.md)",
                "- [Стресс по затратам](COST_STRESS.md)",
                "- [Повторяемость по годам](../execute/research/PATTERNS.md)",
                "- [Скриншот TradingView LKOH](../execute/evidence/LKOH_tradingview_2026-10-31.png)", "",
                "Базовая стратегия [12/33](../execute/strategy.pine); [скрипт сравнения направлений и пар](../execute/variants.pine).", ""]
    (SUCCESS / "README.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"ticker READMEs={len(by_symbol)}; success rows={len(candidates)}; success symbols={len(set(r['symbol'] for r in candidates))}")


if __name__ == "__main__":
    main()
