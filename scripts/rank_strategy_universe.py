"""Rank stocks for every frozen rule without tuning parameters per stock."""

from __future__ import annotations

import csv
import gzip
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from criteria.screen_historical import screen
from src.research.strategy_robustness import run as recalculate_robustness
from src.research.timeframes import source_path

CATALOG = ROOT / "strategies/catalog.json"
OUTPUT = ROOT / "strategies/rankings.json"
REPORT = ROOT / "strategies/RANKINGS.md"


def liquidity(symbols: list[str]) -> tuple[dict[str, float], float]:
    """Median daily close × shares over the last 60 observed trading days."""
    values = {}
    for symbol in symbols:
        path = source_path(ROOT / "data/moex_scan", symbol, "1D")
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        recent = [float(row["close"]) * float(row.get("volume", 0) or 0)
                  for row in rows[-60:]]
        if len(recent) >= 40:
            values[symbol] = round(statistics.median(recent), 2)
    ranked = sorted(values.values())
    threshold = ranked[int(.75 * (len(ranked) - 1))]
    return values, threshold


def selector_token(selector: dict) -> str:
    if "variant" in selector:
        return f",{selector['variant']},"
    if "rule_id" in selector:
        return f",{selector['rule_id']},"
    return f",{selector['fast']},{selector['slow']},{selector['mode']},"


def rows_for_rules(experiment: str, timeframe: str, rules: list[dict]):
    folder = ROOT / "experiments" / experiment / "results" / timeframe
    tokens = {rule["id"]: selector_token(rule["selector"]) for rule in rules}
    for path in sorted(folder.glob("*.csv*")):
        if not path.name.endswith((".csv", ".csv.gz")):
            continue
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader([next(stream)]))
            for line in stream:
                matched = [rule for rule in rules if tokens[rule["id"]] in line]
                if not matched:
                    continue
                values = next(csv.reader([line]))
                if len(values) != len(header):
                    raise ValueError(f"bad CSV row in {path}")
                row = dict(zip(header, values))
                for rule in matched:
                    if all(str(row.get(key)) == str(value) for key, value in rule["selector"].items()):
                        yield rule["id"], row, str(path.relative_to(ROOT))


def build() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "experiments/ema-levels-grid-search/results/manifest.json").read_text())
    liquidity_by_symbol, minimum = liquidity(manifest["symbols"])
    setups = defaultdict(list)
    for path in (ROOT / "papertrading/setups/fleet").glob("*.json"):
        setup = json.loads(path.read_text(encoding="utf-8"))
        setups[setup["strategy"]].append(setup["symbol"])
    grouped = defaultdict(list)
    for rule in catalog["rules"]:
        if rule["selector"] is not None:
            grouped[(rule["experiment"], rule["timeframe"])].append(rule)
    found = defaultdict(list)
    for (experiment, timeframe), rules in grouped.items():
        for rule_id, row, path in rows_for_rules(experiment, timeframe, rules):
            found[rule_id].append((row, path))
    results = []
    for rule in catalog["rules"]:
        current = found[rule["id"]]
        if rule["selector"] is None:
            results.append({**rule, "status": "NO_CROSS_TICKER_RESULTS", "tested_tickers": 0,
                            "top10": [], "active_paper_symbols": sorted(setups[rule["id"]])})
            continue
        if len({row["symbol"] for row, _ in current}) != len(current):
            raise ValueError(f"duplicate ticker result for {rule['id']}")
        all_returns = [float(row["net_return_pct"]) for row, _ in current]
        eligible = []
        for row, path in current:
            symbol = row["symbol"]
            turnover = liquidity_by_symbol.get(symbol)
            if turnover is None or turnover < minimum or screen(row):
                continue
            eligible.append({"symbol": symbol,
                             "net_return_pct": float(row["net_return_pct"]),
                             "median_60d_turnover_rub": turnover,
                             "closed_trades": int(row["closed_trades"]),
                             "late_trades": int(row.get("late_trades", row.get("oos_trades", 0))),
                             "late_return_pct": float(row.get("late_return_pct", row.get("oos_return_pct", 0))),
                             "profit_factor": float(row["profit_factor"]),
                             "max_drawdown_pct": float(row["max_drawdown_pct"]),
                             "source_csv": path,
                             "paper_active": symbol in setups[rule["id"]]})
        eligible.sort(key=lambda x: (-x["net_return_pct"], -x["median_60d_turnover_rub"], x["symbol"]))
        results.append({**rule, "status": "HISTORICAL_RANKING",
                        "tested_tickers": len(all_returns),
                        "median_return_pct": round(statistics.median(all_returns), 2) if all_returns else None,
                        "profitable_tickers": sum(x > 0 for x in all_returns),
                        "liquid_screened_tickers": len(eligible),
                        "top10": eligible[:10],
                        "active_paper_symbols": sorted(setups[rule["id"]])})
    return {"snapshot": catalog["source_snapshot"],
            "liquidity_method": "median of close*volume on last 60 daily candles",
            "liquidity_minimum_rub": minimum,
            "liquidity_universe_tickers": len(liquidity_by_symbol),
            "ranking_note": "Fixed rule on all available tickers; top10 after historical screen and turnover gate. Late period is seen history. Short borrow and dividends are unverified. Largest trade contribution is not checked.",
            "rules": results}


def markdown(data: dict) -> str:
    lines = ["# Топ-10 акций для каждого фиксированного правила", "",
             "Сформировано командой `python3 scripts/rank_strategy_universe.py` из сохранённых свечей и полных CSV экспериментов. "
             "Параметры каждого правила одинаковы на всех акциях; тикер не участвует в подборе параметров.", "",
             f"Высокий оборот: медиана дневного `close × volume` за последние 60 торговых дней "
             f"не ниже {data['liquidity_minimum_rub']:,.0f} ₽ (верхняя четверть из "
             f"{data['liquidity_universe_tickers']} акций с данными). Это фильтр исполнимости, "
             "а не доказательство доходности.", "",
             "Рейтинг строится по доходности после исторического фильтра: ≥100 сделок, ≥30 в позднем периоде, "
             "положительный результат в обоих периодах, PF >1,2 и просадка не глубже 20%. "
             "Поздний период уже просмотрен. Заём short и дивиденды не учтены; вклад одной крупной сделки "
             "пока не проверен. Наличие акции в таблице не запускает paper trading.", ""]
    for rule in data["rules"]:
        lines += [f"## [{rule['id']}]({rule['id']}/README.md)", ""]
        if rule["status"] != "HISTORICAL_RANKING":
            lines += [rule.get("limitation", "Нет сопоставимого расчёта по разным акциям."), ""]
            continue
        lines += [f"{rule['timeframe']}: медиана по {rule['tested_tickers']} акциям "
                  f"{rule['median_return_pct']:+.2f}%; прибыльных {rule['profitable_tickers']}; "
                  f"прошли фильтр и оборот {rule['liquid_screened_tickers']}.", "",
                  "| Акция | Доходность | Сделок | Поздняя доходность | Медианный оборот 60д | Paper |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
        for row in rule["top10"]:
            lines.append(f"| [{row['symbol']}](../{row['source_csv']}) | "
                         f"{row['net_return_pct']:+.2f}% | {row['closed_trades']} | "
                         f"{row['late_return_pct']:+.2f}% | "
                         f"{row['median_60d_turnover_rub']:,.0f} ₽ | "
                         f"{'да' if row['paper_active'] else 'нет'} |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    report = build()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(markdown(report), encoding="utf-8")
    for rule in report["rules"]:
        folder = ROOT / "strategies" / rule["id"]
        (folder / "selection.json").write_text(
            json.dumps({"snapshot": report["snapshot"],
                        "liquidity_minimum_rub": report["liquidity_minimum_rub"],
                        "liquidity_method": report["liquidity_method"], **rule},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    recalculate_robustness([])
    print(f"{OUTPUT}\n{REPORT}")
