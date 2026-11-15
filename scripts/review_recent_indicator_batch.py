"""Compare selected paper candidates with the same rule's broad results and control."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = ("trendoscope", "aroon", "williams", "stoch", "keltner",
            "ichimoku", "mfi", "cmf", "dmi", "cci")
MARKER = "\n## Аналитическое ревью после автоматического отбора\n"
WINDOW_START = "2025-10"
WINDOW_END = "2026-09"


def experiment_for(family: str) -> Path:
    if family == "trendoscope":
        return ROOT / "experiments/trendoscope/band-based-trend-filter-breakout"
    return next((ROOT / "experiments" / family).glob("*/protocol.json")).parent


def window_return(rows: list[dict]) -> float | None:
    rows = sorted(rows, key=lambda item: item["start"])
    if len(rows) != 12 or rows[0]["start"][:7] != WINDOW_START or rows[-1]["start"][:7] != WINDOW_END:
        return None
    return 100 * (float(rows[-1]["ending_equity_rub"]) / float(rows[0]["starting_equity_rub"]) - 1)


def summary(family: str) -> dict:
    experiment = experiment_for(family)
    result = experiment / "results"
    review = json.loads((result / "paper_review.json").read_text())
    rule = review["rule"]
    symbols = {item["symbol"] for item in review["stocks"]}
    rows: dict[tuple[str, str], list[dict]] = {}
    with (result / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        for item in csv.DictReader(stream):
            if (item["timeframe"] == rule["timeframe"]
                    and item["variant"] in (rule["variant"], "baseline")
                    and WINDOW_START <= item["start"][:7] <= WINDOW_END):
                rows.setdefault((item["symbol"], item["variant"]), []).append(item)
    all_returns = [value for (symbol, variant), records in rows.items()
                   if variant == rule["variant"]
                   for value in [window_return(records)] if value is not None]
    chosen_returns = []
    chosen_controls = []
    wins_control = 0
    for symbol in symbols:
        own = window_return(rows.get((symbol, rule["variant"]), []))
        control = window_return(rows.get((symbol, "baseline"), []))
        if own is not None and control is not None:
            chosen_returns.append(own)
            chosen_controls.append(control)
            wins_control += own > control
    years = {"2024": [], "2025": []}
    with (result / "yearly_returns.csv").open(newline="", encoding="utf-8") as stream:
        for item in csv.DictReader(stream):
            if (item["symbol"] in symbols and item["timeframe"] == rule["timeframe"]
                    and item["variant"] == rule["variant"] and item["year"] in years):
                years[item["year"]].append(float(item["return_pct"]))
    return {"experiment": experiment, "rule": rule, "selected": len(symbols),
            "universe_count": len(all_returns), "universe_median_12m": statistics.median(all_returns),
            "universe_positive_count": sum(value > 0 for value in all_returns),
            "chosen_median_12m": statistics.median(chosen_returns),
            "control_median_12m": statistics.median(chosen_controls),
            "chosen_beat_control": wins_control, "chosen_control_pairs": len(chosen_returns),
            "years": years}


def write_review(family: str) -> dict:
    item = summary(family)
    target = item["experiment"] / "results/PAPER_REVIEW.md"
    body = target.read_text(encoding="utf-8")
    if MARKER in body:
        body = body.split(MARKER, 1)[0].rstrip() + "\n"
    year_lines = []
    for year, values in item["years"].items():
        median = f"{statistics.median(values):+.2f}%" if values else "—"
        year_lines.append(f"| {year} | {len(values)} | {sum(value > 0 for value in values)} | {sum(value > 10 for value in values)} | {median} |")
    verdict = ("Медиана всей вселенной за последние 12 месяцев отрицательна; выбранные акции были исключениями."
               if item["universe_median_12m"] < 0 else
               "Медиана всей вселенной ниже порога 10%; результат выбранных акций не переносится автоматически на другие бумаги.")
    note = f'''{MARKER}
Последние **полные** 12 месяцев: октябрь 2025 — сентябрь 2026. Доходность после модельных расходов; исходная и поздняя история уже использованы при выборе и не являются независимой проверкой.

| Срез | Наблюдений | Медиана за 12 месяцев | Положительных |
| --- | ---: | ---: | ---: |
| Вся доступная вселенная, одна выбранная настройка | {item["universe_count"]} | {item["universe_median_12m"]:+.2f}% | {item["universe_positive_count"]} |
| Отобранные акции | {item["selected"]} | {item["chosen_median_12m"]:+.2f}% | {item["selected"]} |
| Контроль buy-and-hold на тех же акциях, 25% капитала | {item["chosen_control_pairs"]} | {item["control_median_12m"]:+.2f}% | — |

Отобранный вариант опередил контроль на **{item["chosen_beat_control"]} из {item["chosen_control_pairs"]}** акций за этот же просмотренный год.

### Предыдущие полные годы на отобранных акциях

| Год | Полных историй | Год в плюсе | Выше 10% | Медиана |
| --- | ---: | ---: | ---: | ---: |
{chr(10).join(year_lines)}

**Вывод:** {verdict} Регистрация счетов означает только виртуальную проверку. Для вывода об устойчивости нужны новые наблюдения после даты снимка, проверенные корпоративные события и стоимость займа short. Сверка Python проверяла адаптер против той же исследовательской функции; независимой сверки Pine-сделок с TradingView пока нет.
'''
    target.write_text(body.rstrip() + "\n" + note.rstrip() + "\n", encoding="utf-8")
    return item


if __name__ == "__main__":
    for family in FAMILIES:
        result = write_review(family)
        print(family, result["selected"], round(result["universe_median_12m"], 2))
