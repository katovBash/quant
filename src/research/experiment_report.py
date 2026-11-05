"""Write a readable, reproducible monthly report from experiment result rows."""

from __future__ import annotations

import csv
import json
import re
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from src.research.annual_returns import calendar_years
from src.research.combination_review import report_section as combination_section


def _money(value: float | None) -> str:
    return "—" if value is None else f"{value:,.0f}".replace(",", " ") + " ₽"


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 2) if values else None


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _recent_month_average(months: list[dict], length: int) -> tuple[float | None, float | None]:
    """Mean per complete calendar month, only for a contiguous trailing window."""
    tail = months[-length:]
    if len(tail) != length:
        return None, None
    indices = []
    for item in tail:
        stamp = date.fromisoformat(item["start"][:10])
        indices.append(stamp.year * 12 + stamp.month)
    if any(right - left != 1 for left, right in zip(indices, indices[1:])):
        return None, None
    return (_mean([float(item["pnl_rub"]) for item in tail]),
            _mean([float(item["return_pct"]) for item in tail]))


def _side_analysis(output: Path) -> str:
    path = output / "trade_side_summary.csv"
    if not path.is_file():
        return ("Разбивка закрытых сделок по направлениям пока не рассчитана. "
                "Вывод о long или short не делается; нужен журнал сделок с полем `side` "
                "и отдельный пересчёт вариантов только long и только short.")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return "Разбивка по направлениям пуста; вывод о long или short не делается."
    lines = ["Доля удачных сделок считается **только по закрытым сделкам**. "
             "Доходность включает переоценку открытой позиции и потому не выводится из этой доли. "
             "Сравнение направлений проведено на уже просмотренной истории; это гипотеза для отдельной проверки.", "",
             "| Акция · интервал · вариант | Режим | Закрыто long / выигрыш | Закрыто short / выигрыш | Плюсовые месяцы | Вывод |",
             "|---|---|---:|---:|---:|---|"]
    for row in rows:
        long_count = int(row["long_closed"])
        short_count = int(row["short_closed"])
        long_win = (f"{int(row['long_wins'])}/{long_count} · {100*int(row['long_wins'])/long_count:.1f}%"
                    if long_count else "0 · —")
        short_win = (f"{int(row['short_wins'])}/{short_count} · {100*int(row['short_wins'])/short_count:.1f}%"
                     if short_count else "0 · —")
        lines.append(f"| {row['symbol']} · {row['timeframe']} · `{row['variant']}` | "
                     f"{row['mode']} | {long_win} | {short_win} | "
                     f"{row['profitable_months']}/{row['months']} | {row.get('conclusion', '—')} |")
    lines += ["", "[Все результаты по направлениям](trade_side_summary.csv). "
              "Если капитал уходит ниже нуля, вариант недопустим независимо от процента успешных сделок."]
    return "\n".join(lines)


def build_report(output: Path, protocol: dict, summary: dict,
                 rows: list[dict], monthly_rows: list[dict]) -> None:
    """Keep every pair in CSV; Markdown highlights examples without hiding failures."""
    if not rows:
        raise ValueError("Cannot build an experiment report without result rows")
    by_pair: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in monthly_rows:
        by_pair[(item["symbol"], item["timeframe"], item["variant"])].append(item)
    baselines = {(row["symbol"], row["timeframe"]): row
                 for row in rows if row["variant"] == "baseline"}
    cases = []
    for row in rows:
        months = sorted(by_pair[(row["symbol"], row["timeframe"], row["variant"])],
                        key=lambda item: item["start"])
        pnls = [float(item["pnl_rub"]) for item in months]
        returns = [float(item["return_pct"]) for item in months]
        positive = [value for value in pnls if value > 0]
        negative = [value for value in pnls if value < 0]
        losing_streak = max_streak = 0
        for value in pnls:
            losing_streak = losing_streak + 1 if value <= 0 else 0
            max_streak = max(max_streak, losing_streak)
        base = baselines.get((row["symbol"], row["timeframe"]))
        base_months = by_pair.get((row["symbol"], row["timeframe"], "baseline"), [])
        base_pnls = [float(item["pnl_rub"]) for item in base_months]
        late = [item for item in months if item.get("sample") != "train"]
        recent = {length: _recent_month_average(months, length) for length in (1, 3, 6, 9, 12)}
        annual = calendar_years(months)
        latest_year = annual[-1] if annual else None
        baseline_annual = next((year for year in calendar_years(base_months)
                                if latest_year and year["year"] == latest_year["year"]
                                and year["first_month"] == latest_year["first_month"]
                                and year["last_month"] == latest_year["last_month"]), None)
        cases.append({"symbol": row["symbol"], "timeframe": row["timeframe"],
                      "variant": row["variant"], "months": len(months),
                      "profitable_months": len(positive),
                      "losing_months": len(negative),
                      "zero_months": len(months) - len(positive) - len(negative),
                      "profitable_month_share_pct": round(100 * len(positive) / len(months), 2)
                                                    if months else None,
                      "mean_month_pnl_rub": _mean(pnls),
                      "mean_month_return_pct": _mean(returns),
                      **{f"last_{length}m_mean_month_pnl_rub": recent[length][0]
                         for length in (1, 3, 6, 9, 12)},
                      **{f"last_{length}m_mean_month_return_pct": recent[length][1]
                         for length in (1, 3, 6, 9, 12)},
                      "median_month_pnl_rub": round(statistics.median(pnls), 2) if pnls else None,
                      "mean_profitable_month_pnl_rub": _mean(positive),
                      "mean_profitable_month_return_pct": _mean([
                          float(item["return_pct"]) for item in months if float(item["pnl_rub"]) > 0]),
                      "mean_losing_month_pnl_rub": _mean(negative),
                      "mean_losing_month_return_pct": _mean([
                          float(item["return_pct"]) for item in months if float(item["pnl_rub"]) < 0]),
                      "worst_month_pnl_rub": min(pnls) if pnls else None,
                      "best_month_pnl_rub": max(pnls) if pnls else None,
                      "max_consecutive_nonpositive_months": max_streak,
                      "closed_trades_in_months": sum(int(item["closed_trades"]) for item in months),
                      "late_profitable_months": sum(float(item["pnl_rub"]) > 0 for item in late),
                      "late_months": len(late),
                      "full_period_pnl_rub": row["pnl_rub"],
                      "full_period_return_pct": row["net_return_pct"],
                      "latest_calendar_year": latest_year["year"] if latest_year else None,
                      "latest_year_complete": latest_year["complete"] if latest_year else None,
                      "latest_year_pnl_rub": latest_year["pnl_rub"] if latest_year else None,
                      "latest_year_return_pct": latest_year["return_pct"] if latest_year else None,
                      "baseline_profitable_months": sum(value > 0 for value in base_pnls)
                      if base_pnls else None,
                      "baseline_worst_month_pnl_rub": min(base_pnls) if base_pnls else None,
                      "baseline_full_period_pnl_rub": base["pnl_rub"] if base else None})
        cases[-1]["baseline_latest_year_pnl_rub"] = baseline_annual["pnl_rub"] if baseline_annual else None
    path = output / "monthly_case_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cases[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(cases)

    filtered = [item for item in cases if item["variant"] != "baseline"]
    top = sorted((item for item in filtered if item["months"]), key=lambda item: (item["profitable_months"],
                                             item["worst_month_pnl_rub"],
                                             float(item["latest_year_pnl_rub"] or 0)), reverse=True)[:10]
    compared = [item for item in filtered
                if item["baseline_profitable_months"] is not None
                and item["baseline_worst_month_pnl_rub"] is not None
                and item["baseline_latest_year_pnl_rub"] is not None
                and item["worst_month_pnl_rub"] is not None]
    improvements = sum(
        item["profitable_months"] > int(item["baseline_profitable_months"])
        and item["worst_month_pnl_rub"] > float(item["baseline_worst_month_pnl_rub"])
        and float(item["latest_year_pnl_rub"]) > float(item["baseline_latest_year_pnl_rub"])
        for item in compared)
    kind = ("непрерывный счёт с переоценкой открытых позиций"
            if protocol.get("primary_evaluation") == "monthly" else
            "отдельный счёт, запущенный в начале каждого месяца")
    comparison = (f"Вариантов с дополнительным правилом: {len(filtered)}. "
                  + (f"Из {len(compared)} сопоставимых с контролем вариантов у {improvements} "
                     "одновременно больше прибыльных месяцев, мягче худший месяц "
                     "и выше PnL за последний сопоставимый календарный год или YTD. " if compared else
                     "Сопоставимых вариантов с контролем нет. ")
                  + "Это сравнение на просмотренной истории, без автоматического допуска.")
    group_rows = []
    for timeframe in protocol["signal_timeframes"]:
        for label, subset in (("Контроль", [item for item in cases
                                        if item["timeframe"] == timeframe and item["variant"] == "baseline"]),
                              ("Остальные варианты", [item for item in filtered
                                              if item["timeframe"] == timeframe])):
            if subset:
                with_months = [item for item in subset if item["months"]]
                if not with_months:
                    continue
                median_share = statistics.median(item["profitable_month_share_pct"] for item in with_months)
                mean_month = statistics.mean(item["mean_month_pnl_rub"] for item in with_months)
                mean_return = statistics.mean(item["mean_month_return_pct"] for item in with_months)
                group_rows.append(f"| {timeframe} · {label} | {len(subset)} | {median_share:.1f}% | "
                                  f"{_money(mean_month)} · {_percent(mean_return)} |")
    case_rows = []
    annual_rows = []
    for item in top:
        case_rows.append(f"| {item['symbol']} · {item['timeframe']} · `{item['variant']}` | "
                         f"{item['profitable_months']} / {item['months']} | "
                         f"{_money(item['mean_month_pnl_rub'])} · "
                         f"{_percent(item['mean_month_return_pct'])} | "
                         f"{_money(item['mean_profitable_month_pnl_rub'])} / "
                         f"{_money(item['mean_losing_month_pnl_rub'])} | "
                         f"{_money(item['worst_month_pnl_rub'])} | "
                         f"{item['latest_calendar_year']}{'' if item['latest_year_complete'] else ' YTD'}: "
                         f"{_money(item['latest_year_pnl_rub'])} · "
                         f"{_percent(item['latest_year_return_pct'])} | "
                         f"{item['baseline_profitable_months'] if item['baseline_profitable_months'] is not None else '—'} / {item['months']} |")
        pair = (item["symbol"], item["timeframe"], item["variant"])
        for annual in calendar_years(by_pair[pair]):
            period = annual["year"] if annual["complete"] else (
                f"{annual['year']} · {annual['first_month']:02d}–{annual['last_month']:02d} (неполный)")
            annual_rows.append(f"| {item['symbol']} · {item['timeframe']} · `{item['variant']}` | "
                               f"{period} | {annual['months']} | {_money(annual['pnl_rub'])} | "
                               f"{_percent(annual['return_pct'])} |")
    phase_link = (" и [разбивка по фазам](monthly_regime_profiles.csv)"
                  if (output / "monthly_regime_profiles.csv").exists() else "")
    recent_rows = []
    for item in top:
        cells = [f"{_money(item[f'last_{length}m_mean_month_pnl_rub'])} · "
                 f"{_percent(item[f'last_{length}m_mean_month_return_pct'])}"
                 for length in (1, 3, 6, 9, 12)]
        recent_rows.append(f"| {item['symbol']} · {item['timeframe']} · `{item['variant']}` | "
                           + " | ".join(cells) + " |")
    monthly_grid_rows = []
    for item in top:
        pair = (item["symbol"], item["timeframe"], item["variant"])
        by_year: dict[str, dict[int, float]] = defaultdict(dict)
        for month in by_pair[pair]:
            stamp = date.fromisoformat(month["start"][:10])
            by_year[str(stamp.year)][stamp.month] = float(month["return_pct"])
        for year, monthly_values in sorted(by_year.items()):
            cells = []
            for number in range(1, 13):
                value = monthly_values.get(number)
                marker = "🟩" if value is not None and value > 0 else "🟥" if value is not None and value < 0 else "⬜"
                cells.append(f"{marker} {_percent(value)}" if value is not None else "—")
            monthly_grid_rows.append(
                f"| {item['symbol']} · {item['timeframe']} · `{item['variant']}` | {year} | "
                + " | ".join(cells) + " |")
    template = (Path(__file__).resolve().parents[2] / "experiments/template/REPORT.template.md")
    report = template.read_text(encoding="utf-8")
    fields = {
        "STRATEGY_HISTORY_LINK": (
            "Накопленная доходность выбранных стратегий за последние полные 1, 3, 6, 9 и 12 месяцев: "
            "[STRATEGY_HISTORY.md](STRATEGY_HISTORY.md)."
            if (output / "STRATEGY_HISTORY.md").exists() else ""),
        "SOURCE_SNAPSHOT": protocol.get("source_snapshot", "не указан"),
        "MONTHLY_METHOD": kind,
        "COST_MODEL": summary.get("cost_model", "не указана"),
        "CORPORATE_STATUS": (
            "выплаты и сплиты проверены для всей выборки и применены в расчёте"
            if protocol.get("corporate_actions", {}).get("status") == "complete"
            and protocol.get("corporate_actions", {}).get("applied_in_main_results")
            else "покрытие неполное или выплаты не применены; результат REVIEW_ONLY"),
        "SYMBOL_COUNT": len({row["symbol"] for row in rows}),
        "TIMEFRAMES": ", ".join(protocol["signal_timeframes"]),
        "PAIR_COUNT": len(rows),
        "ERROR_COUNT": len(summary.get("errors", [])),
        "COMPARISON_SUMMARY": comparison,
        "GROUP_ROWS": "\n".join(group_rows),
        "COMBINATION_SECTION": combination_section(protocol, rows, by_pair),
        "CASE_ROWS": "\n".join(case_rows),
        "ANNUAL_ROWS": "\n".join(annual_rows),
        "RECENT_ROWS": "\n".join(recent_rows),
        "MONTHLY_GRID_ROWS": "\n".join(monthly_grid_rows),
        "SIDE_ANALYSIS": _side_analysis(output),
        "PHASE_LINK": phase_link,
    }
    report = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: str(fields[match.group(1)]), report)
    attribution = protocol.get("trader_attribution")
    if attribution:
        report += ("\n## Источник торговой идеи\n\n"
                   f"Автор: {attribution['name']}. "
                   f"[Первоисточник]({attribution['source_url']}). "
                   f"Тип свидетельства: `{attribution['source_type']}`.\n\n"
                   f"Механическое правило этого теста: {attribution['rule_interpretation']}\n\n"
                   "Полный личный журнал сделок не подтверждён; результаты выше относятся "
                   "только к проверке сформулированной версии на локальных свечах.\n")
    event_study = output / "event_study_summary.json"
    if event_study.is_file():
        evidence = json.loads(event_study.read_text(encoding="utf-8"))
        report += ("\n## Событийная проверка по датам ЦБ\n\n"
                   "Плановая публикация 13:30 МСК; сравнение первого полного часа "
                   "14:00–15:00 с тем же часом за семь дней до каждого решения на тех же акциях. "
                   "Акции одного дня не являются независимыми наблюдениями. "
                   "Это реакция вокруг события, а не доказательство причинного влияния ставки.\n\n"
                   f"Сопоставлено {evidence['matched_events']} из "
                   f"{evidence['scheduled_events']} дат и "
                   f"{evidence['matched_stock_event_pairs']} пар акция × событие. "
                   f"Положительная медианная разница абсолютного движения на "
                   f"{evidence['dates_with_larger_median_abs_move']} датах; "
                   f"медиана разниц по датам "
                   f"{evidence['median_of_event_date_median_abs_difference_pp']:+.4f} п.п.; "
                   f"медиана отношения объёмов "
                   f"{evidence['median_of_event_date_median_volume_ratio']}.\n\n"
                   "[Все пары](event_study.csv) · "
                   "[разбивка по датам](event_date_summary.csv) · "
                   "[пропуски](event_study_missing.csv) · "
                   "[календарь](../events.json).\n")
    decision_study = output / "decision_event_summary.json"
    if decision_study.is_file():
        evidence = json.loads(decision_study.read_text(encoding="utf-8"))
        counts = evidence["rate_decision_counts"]
        report += ("\n## После опубликованного решения ЦБ\n\n"
                   f"Проверено {evidence['scheduled_decision_dates']} независимых дат: "
                   f"повышений {counts['hike']}, снижений {counts['cut']}, "
                   f"без изменения {counts['hold']}. Направление сделки задано "
                   "фактическим решением, а не движением свечи. Вход после "
                   "полного часа 14:00–15:00 МСК. Ожидания рынка до публикации "
                   "не известны, поэтому изменение ставки не равно сюрпризу.\n\n"
                   "| Правило | Дат с данными | Дат с положительной медианой | "
                   "Медиана по датам, % счёта |\n|---|---:|---:|---:|\n")
        for variant, values in evidence["variant_dates"].items():
            report += (f"| `{variant}` | {values['dates']} | "
                       f"{values['positive_date_medians']} | "
                       f"{values['median_of_date_medians_pct']:+.4f}% |\n")
        report += ("\n[Решения и источники](../decisions.json) · "
                   "[каждая сделка вокруг события](decision_outcomes.csv) · "
                   "[итог по датам](decision_date_summary.csv). "
                   "Акции одной даты зависимы; доходность отдельной модельной сделки "
                   "здесь приблизительная, точный месячный счёт показан выше.\n")
    (output / "REPORT.md").write_text(report, encoding="utf-8")
