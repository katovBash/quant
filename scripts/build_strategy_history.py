"""Build compact dashboard history from each strategy's frozen research CSVs."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.recent_returns import trailing_period
from src.research.annual_returns import calendar_years

STRATEGIES = ROOT / "strategies"


def selected_rows(path: Path, symbols: set[str], timeframe: str, variant: str) -> dict[str, dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return {row["symbol"]: row for row in csv.DictReader(stream)
                if row["symbol"] in symbols and row["timeframe"] == timeframe
                and row["variant"] == variant}


def selected_months(path: Path, symbols: set[str], timeframe: str, variant: str) -> dict[str, list[dict]]:
    result = {symbol: [] for symbol in symbols}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["symbol"] in symbols and row["timeframe"] == timeframe and row["variant"] == variant:
                result[row["symbol"]].append(row)
    return result


def build_strategy(strategy_dir: Path) -> dict:
    selection = json.loads((strategy_dir / "selection.json").read_text(encoding="utf-8"))
    symbols = {row["symbol"] for row in selection["top10"]}
    if not symbols:
        raise ValueError(f"no selected symbols: {strategy_dir.name}")
    result = {"strategy_id": selection["id"], "symbols": {symbol: {} for symbol in sorted(symbols)}}
    for mode, source in selection["history_sources"].items():
        if mode not in ("before", "after"):
            raise ValueError(f"unsupported cost mode: {mode}")
        source_rows = selected_rows(ROOT / source["all_variants_csv"], symbols,
                                    source["timeframe"], source["variant"])
        monthly = selected_months(ROOT / source["monthly_csv"], symbols,
                                  source["timeframe"], source["variant"])
        if set(source_rows) != symbols or any(not monthly[symbol] for symbol in symbols):
            raise ValueError(f"incomplete research source: {strategy_dir.name} {mode}")
        for symbol in symbols:
            row = source_rows[symbol]
            ordered_months = sorted(monthly[symbol], key=lambda item: item["start"])
            month_ids = [item["start"][:7] for item in ordered_months]
            if len(month_ids) != len(set(month_ids)):
                raise ValueError(f"duplicate complete month: {strategy_dir.name} {mode} {symbol}")
            periods = {str(length): trailing_period(ordered_months, length)
                       for length in (1, 3, 6, 9, 12)}
            annual = calendar_years(ordered_months)
            result["symbols"][symbol][mode] = {
                "closed_trades": int(row["closed_trades"]),
                "last_complete_month": month_ids[-1],
                "periods": periods,
                "calendar_years": annual,
                "months": [{"month": item["start"][:7],
                            "return_pct": round(float(item["return_pct"]), 2),
                            "pnl_rub": round(float(item["pnl_rub"]), 2),
                            "closed_trades": int(item["closed_trades"])}
                           for item in ordered_months]}
    return result


def format_return(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def write_experiment_reports(grouped: dict[Path, list[tuple[dict, dict]]]) -> None:
    for report_path, strategies in grouped.items():
        lines = ["# Доходность выбранных стратегий по последним периодам", "",
                 "Накопленная доходность по непрерывному виртуальному счёту за последние полные "
                 "1, 3, 6, 9 и 12 календарных месяцев. Это не средняя доходность за месяц. "
                 "Годовой PnL считается отдельно по каждому календарному году; текущий год помечен YTD.", ""]
        for selection, snapshot in strategies:
            lines += [f"## {selection['id']} · {selection['timeframe']}", ""]
            for mode, label in (("after", "После расходов"), ("before", "До расходов")):
                if mode not in selection["history_sources"]:
                    if mode == "after":
                        lines += ["Расчёт после расходов для этого правила отсутствует.", ""]
                    continue
                source = selection["history_sources"][mode]
                source_path = ROOT / source["monthly_csv"]
                lines += [f"### {label}", "",
                          f"Источник: [{source_path.name}]({os.path.relpath(source_path, report_path.parent)})"]
                lines += ["", "| Акция | Последний календарный год / YTD | 1 месяц | 3 месяца | 6 месяцев | 9 месяцев | 12 месяцев | Сделки | Последний полный месяц |",
                          "|---|---:|---:|---:|---:|---:|---:|---:|---|" ]
                for selected in selection["top10"]:
                    row = snapshot["symbols"][selected["symbol"]][mode]
                    periods = row["periods"]
                    values = [format_return(periods[str(n)]["return_pct"] if periods[str(n)] else None)
                              for n in (1, 3, 6, 9, 12)]
                    latest_year = row["calendar_years"][-1]
                    annual_text = (f"{latest_year['year']}{'' if latest_year['complete'] else ' YTD'}: "
                                   f"{format_return(latest_year['return_pct'])} · "
                                   f"{latest_year['pnl_rub']:,.0f} ₽".replace(",", " "))
                    lines.append("| " + " | ".join([selected["symbol"], annual_text,
                                                      *values, str(row["closed_trades"]), row["last_complete_month"]]) + " |")
                lines += ["", "#### PnL по календарным годам", "",
                          "Неполный год показан только по завершённым месяцам.", "",
                          "| Акция | Год | Месяцев | PnL | Доходность |",
                          "|---|---|---:|---:|---:|"]
                for selected in selection["top10"]:
                    for annual in snapshot["symbols"][selected["symbol"]][mode]["calendar_years"]:
                        year = annual["year"] + ("" if annual["complete"] else " YTD")
                        money = f"{annual['pnl_rub']:,.0f} ₽".replace(",", " ")
                        lines.append(f"| {selected['symbol']} | {year} | {annual['months']} | "
                                     f"{money} | {format_return(annual['return_pct'])} |")
                lines += ["", "#### Каждый полный месяц", "",
                          "В ячейке — доходность именно этого месяца по счёту с переоценкой открытой позиции. "
                          "Знак и значение относятся к выбранному режиму расходов.", "",
                          "| Акция | Год | Янв | Фев | Мар | Апр | Май | Июн | Июл | Авг | Сен | Окт | Ноя | Дек |",
                          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
                for selected in selection["top10"]:
                    symbol = selected["symbol"]
                    year_months = {}
                    for month in snapshot["symbols"][symbol][mode]["months"]:
                        year, number = month["month"].split("-")
                        year_months.setdefault(year, {})[int(number)] = month["return_pct"]
                    for year, values in sorted(year_months.items()):
                        cells = [format_return(values.get(number)) for number in range(1, 13)]
                        lines.append("| " + " | ".join([symbol, year, *cells]) + " |")
                lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    catalog = json.loads((STRATEGIES / "catalog.json").read_text(encoding="utf-8"))
    grouped = {}
    for rule in catalog["rules"]:
        folder = STRATEGIES / rule["id"]
        selection = json.loads((folder / "selection.json").read_text(encoding="utf-8"))
        if not selection.get("history_sources"):
            continue
        result = build_strategy(folder)
        (folder / "history_snapshot.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        source = selection["history_sources"].get("after") or selection["history_sources"].get("before")
        report_path = ROOT / source["monthly_csv"]
        grouped.setdefault(report_path.parent / "STRATEGY_HISTORY.md", []).append((selection, result))
        print(f"{rule['id']}: {len(result['symbols'])} symbols, {len(selection['history_sources'])} cost modes")
    write_experiment_reports(grouped)


if __name__ == "__main__":
    main()
