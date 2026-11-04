"""Write a readable, reproducible monthly report from experiment result rows."""

from __future__ import annotations

import csv
import re
import statistics
from collections import defaultdict
from pathlib import Path


def _money(value: float | None) -> str:
    return "—" if value is None else f"{value:,.0f}".replace(",", " ") + " ₽"


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 2) if values else None


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


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
        late = [item for item in months if item.get("sample") != "train"]
        cases.append({"symbol": row["symbol"], "timeframe": row["timeframe"],
                      "variant": row["variant"], "months": len(months),
                      "profitable_months": len(positive),
                      "losing_months": len(negative),
                      "zero_months": len(months) - len(positive) - len(negative),
                      "profitable_month_share_pct": round(100 * len(positive) / len(months), 2)
                                                    if months else None,
                      "mean_month_pnl_rub": _mean(pnls),
                      "mean_month_return_pct": _mean(returns),
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
                      "baseline_profitable_months": base["positive_months"] if base else None,
                      "baseline_worst_month_pnl_rub": base["worst_month_pnl_rub"] if base else None,
                      "baseline_full_period_pnl_rub": base["pnl_rub"] if base else None})
    path = output / "monthly_case_summary.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cases[0]))
        writer.writeheader()
        writer.writerows(cases)

    filtered = [item for item in cases if item["variant"] != "baseline"]
    top = sorted((item for item in filtered if item["months"]), key=lambda item: (item["profitable_months"],
                                             item["worst_month_pnl_rub"],
                                             float(item["full_period_pnl_rub"])), reverse=True)[:10]
    compared = [item for item in filtered
                if item["baseline_profitable_months"] is not None
                and item["baseline_worst_month_pnl_rub"] is not None
                and item["baseline_full_period_pnl_rub"] is not None
                and item["worst_month_pnl_rub"] is not None]
    improvements = sum(
        item["profitable_months"] > int(item["baseline_profitable_months"])
        and item["worst_month_pnl_rub"] > float(item["baseline_worst_month_pnl_rub"])
        and float(item["full_period_pnl_rub"]) > float(item["baseline_full_period_pnl_rub"])
        for item in compared)
    kind = ("непрерывный счёт с переоценкой открытых позиций"
            if protocol.get("primary_evaluation") == "monthly" else
            "отдельный счёт, запущенный в начале каждого месяца")
    comparison = (f"Вариантов с дополнительным правилом: {len(filtered)}. "
                  + (f"Из {len(compared)} сопоставимых с контролем вариантов у {improvements} "
                     "одновременно больше прибыльных месяцев, мягче худший месяц "
                     "и выше результат за весь период. " if compared else
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
    for item in top:
        case_rows.append(f"| {item['symbol']} · {item['timeframe']} · `{item['variant']}` | "
                         f"{item['profitable_months']} / {item['months']} | "
                         f"{_money(item['mean_month_pnl_rub'])} · "
                         f"{_percent(item['mean_month_return_pct'])} | "
                         f"{_money(item['mean_profitable_month_pnl_rub'])} / "
                         f"{_money(item['mean_losing_month_pnl_rub'])} | "
                         f"{_money(item['worst_month_pnl_rub'])} | "
                         f"{_money(float(item['full_period_pnl_rub']))} · "
                         f"{_percent(float(item['full_period_return_pct']))} | "
                         f"{item['baseline_profitable_months'] if item['baseline_profitable_months'] is not None else '—'} / {item['months']} |")
    phase_link = (" и [разбивка по фазам](monthly_regime_profiles.csv)"
                  if (output / "monthly_regime_profiles.csv").exists() else "")
    template = (Path(__file__).resolve().parents[2] / "experiments/template/REPORT.template.md")
    report = template.read_text(encoding="utf-8")
    fields = {
        "SOURCE_SNAPSHOT": protocol.get("source_snapshot", "не указан"),
        "MONTHLY_METHOD": kind,
        "COST_MODEL": summary.get("cost_model", "не указана"),
        "SYMBOL_COUNT": len({row["symbol"] for row in rows}),
        "TIMEFRAMES": ", ".join(protocol["signal_timeframes"]),
        "PAIR_COUNT": len(rows),
        "ERROR_COUNT": len(summary.get("errors", [])),
        "COMPARISON_SUMMARY": comparison,
        "GROUP_ROWS": "\n".join(group_rows),
        "CASE_ROWS": "\n".join(case_rows),
        "PHASE_LINK": phase_link,
    }
    report = re.sub(r"\{\{([A-Z_]+)\}\}", lambda match: str(fields[match.group(1)]), report)
    (output / "REPORT.md").write_text(report, encoding="utf-8")
