"""Validate an experiment and review all passing stocks for one fixed rule."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.data_quality import candle_quality
from src.research.annual_returns import calendar_years
from src.research.recent_returns import trailing_period
from src.research.timeframes import source_path
from guardrails.policy import load_policy

CACHE = ROOT / "data/candles/moex_scan"
POLICY = load_policy()["experiment"]
PERIODS = tuple(POLICY["recent_month_windows"])
MIN_UNIVERSE = POLICY["min_eligible_symbols_for_broad_test"]
MIN_TRAIN_MONTHS = POLICY["min_train_months_per_pair_for_ranking"]
MIN_LATE_MONTHS = POLICY["min_late_months_per_pair_for_diagnostics"]
MIN_PAPER_STOCKS = POLICY["min_paper_stocks"]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def monthly_metrics(path: Path) -> dict[tuple[str, str, str], dict]:
    metrics = defaultdict(lambda: {"train_returns": [], "train_pnls": [],
                                   "late_returns": [], "late_pnls": []})
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            key = (row["symbol"], row["timeframe"], row["variant"])
            phase = "train" if row.get("sample") == "train" else "late"
            metrics[key][f"{phase}_returns"].append(float(row["return_pct"]))
            metrics[key][f"{phase}_pnls"].append(float(row["pnl_rub"]))
    return dict(metrics)


def summarize(values: dict) -> dict:
    train = values["train_returns"]
    late = values["late_returns"]
    return {"train_months": len(train),
            "train_positive_share_pct": round(100 * sum(value > 0 for value in train) / len(train), 2) if train else None,
            "train_mean_month_return_pct": round(statistics.mean(train), 2) if train else None,
            "train_worst_month_pnl_rub": round(min(values["train_pnls"]), 2) if train else None,
            "late_months": len(late),
            "late_positive_share_pct": round(100 * sum(value > 0 for value in late) / len(late), 2) if late else None,
            "late_mean_month_return_pct": round(statistics.mean(late), 2) if late else None,
            "late_worst_month_pnl_rub": round(min(values["late_pnls"]), 2) if late else None}


def choose_global_rule(metrics: dict[tuple[str, str, str], dict],
                       min_symbols: int = MIN_UNIVERSE,
                       variant_prefixes: tuple[str, ...] = ()) -> tuple[dict | None, list[dict]]:
    groups = defaultdict(list)
    for (symbol, timeframe, variant), values in metrics.items():
        if variant == "baseline" or (variant_prefixes and
                                     not variant.startswith(variant_prefixes)):
            continue
        item = summarize(values)
        if item["train_months"] >= MIN_TRAIN_MONTHS and item["late_months"] >= MIN_LATE_MONTHS:
            groups[(timeframe, variant)].append({"symbol": symbol, **item})
    candidates = []
    for (timeframe, variant), items in groups.items():
        if len(items) < min_symbols:
            continue
        candidates.append({"timeframe": timeframe, "variant": variant,
                           "symbols": len(items),
                           "median_train_positive_share_pct": round(statistics.median(
                               item["train_positive_share_pct"] for item in items), 2),
                           "median_train_mean_month_return_pct": round(statistics.median(
                               item["train_mean_month_return_pct"] for item in items), 2),
                           "median_train_worst_month_pnl_rub": round(statistics.median(
                               item["train_worst_month_pnl_rub"] for item in items), 2),
                           "median_late_positive_share_pct": round(statistics.median(
                               item["late_positive_share_pct"] for item in items), 2),
                           "median_late_mean_month_return_pct": round(statistics.median(
                               item["late_mean_month_return_pct"] for item in items), 2)})
    candidates.sort(key=lambda item: (-item["median_train_positive_share_pct"],
                                      -item["median_train_mean_month_return_pct"],
                                      -item["median_train_worst_month_pnl_rub"],
                                      -item["symbols"], item["timeframe"], item["variant"]))
    return (candidates[0] if candidates else None), candidates


@lru_cache(maxsize=None)
def turnover_rub(symbol: str) -> float | None:
    path = source_path(CACHE, symbol, "1D")
    if not path.exists():
        return None
    bars = json.loads(path.read_text(encoding="utf-8"))
    values = [float(bar["close"]) * float(bar.get("volume", 0) or 0)
              for bar in bars[-60:] if float(bar["close"]) > 0]
    positive = [value for value in values if value > 0]
    return round(statistics.median(positive), 2) if len(positive) >= 40 else None


def select_stocks(rule: dict, metrics: dict[tuple[str, str, str], dict],
                  result_rows: dict[tuple[str, str, str], dict],
                  limit: int | None = None) -> tuple[list[dict], dict]:
    timeframe, variant = rule["timeframe"], rule["variant"]
    eligible = []
    for (symbol, frame, name), values in metrics.items():
        if (frame, name) != (timeframe, variant):
            continue
        item = summarize(values)
        if item["train_months"] < MIN_TRAIN_MONTHS or item["late_months"] < MIN_LATE_MONTHS:
            continue
        turnover = turnover_rub(symbol)
        if turnover is None:
            continue
        source = result_rows[(symbol, timeframe, variant)]
        eligible.append({"symbol": symbol, **item,
                         "turnover_60d_rub": turnover,
                         "full_return_pct": float(source["net_return_pct"]),
                         "closed_trades": int(source["closed_trades"]),
                         "max_drawdown_pct": float(source["max_drawdown_pct"])})
    if not eligible:
        return [], {"measured_liquidity": 0, "turnover_threshold_rub": None,
                    "liquid_candidates": 0}
    ranked_turnover = sorted(item["turnover_60d_rub"] for item in eligible)
    threshold = ranked_turnover[int((1 - POLICY["liquidity_top_fraction"]) * (len(ranked_turnover) - 1))]
    liquid = [item for item in eligible if item["turnover_60d_rub"] >= threshold]
    liquid.sort(key=lambda item: (-item["train_positive_share_pct"],
                                  -item["train_mean_month_return_pct"],
                                  -item["train_worst_month_pnl_rub"],
                                  -item["turnover_60d_rub"], item["symbol"]))
    return liquid[:limit] if limit is not None else liquid, {"measured_liquidity": len(eligible),
                        "turnover_threshold_rub": threshold,
                        "liquid_candidates": len(liquid)}


def selected_months(path: Path, symbols: set[str], timeframe: str, variant: str) -> dict[str, list[dict]]:
    found = {symbol: [] for symbol in symbols}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row["symbol"] in symbols and row["timeframe"] == timeframe and row["variant"] == variant:
                found[row["symbol"]].append(row)
    return found


def screen_every_rule(candidates: list[dict], metrics: dict, result_rows: dict,
                      monthly_path: Path, cost_status: str) -> list[dict]:
    """Audit every fixed rule; never silently equate one failed rule with a failed grid."""
    recent = defaultdict(lambda: deque(maxlen=12))
    with monthly_path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            recent[(row["symbol"], row["timeframe"], row["variant"])].append(row)
    threshold = POLICY["min_trailing_12m_return_pct_after_costs"]
    costs_ready = cost_status.startswith("after_")
    screening = []
    for rank, rule in enumerate(candidates, 1):
        liquid, liquidity = select_stocks(rule, metrics, result_rows, limit=None)
        qualified = []
        for item in liquid:
            months = sorted(recent[(item["symbol"], rule["timeframe"], rule["variant"])],
                            key=lambda row: row["start"])
            period = trailing_period(months, 12)
            if (costs_ready and period
                    and period.get("return_pct") is not None
                    and period["return_pct"] > threshold):
                qualified.append({"symbol": item["symbol"],
                                  "trailing_12m_return_pct": period["return_pct"]})
        screening.append({"train_rank": rank, "timeframe": rule["timeframe"],
                          "variant": rule["variant"],
                          "liquid_candidates": len(liquid),
                          "passed_trailing_12m": len(qualified) if costs_ready else None,
                          "has_paper_candidates": len(qualified) >= MIN_PAPER_STOCKS,
                          "qualifying_stocks": qualified,
                          "turnover_threshold_rub": liquidity["turnover_threshold_rub"]})
    return screening


def first_passing_rule(candidates: list[dict], screening: list[dict]) -> tuple[dict | None, dict | None]:
    """Keep train rank, using the annual gate only to skip rules with zero candidates."""
    chosen = next((item for item in screening if item["has_paper_candidates"]), None)
    return (candidates[chosen["train_rank"] - 1], chosen) if chosen else (None, None)


def review_focused_rules(requests: list[str], screened: list[dict], metrics: dict,
                         result_rows: dict, monthly_path: Path) -> list[dict]:
    """Detail requested post-hoc alternatives without replacing the primary rule."""
    by_rule = {(row["timeframe"], row["variant"]): row for row in screened}
    reviews = []
    for request in dict.fromkeys(requests):
        timeframe, separator, variant = request.partition(":")
        if not separator or (timeframe, variant) not in by_rule:
            raise ValueError(f"unknown focused rule: {request}")
        screening = by_rule[(timeframe, variant)]
        if screening["passed_trailing_12m"] is None:
            raise ValueError(f"focused review requires after-cost returns: {request}")
        liquid, _ = select_stocks(screening, metrics, result_rows, limit=None)
        qualified_symbols = {row["symbol"] for row in screening["qualifying_stocks"]}
        candidates = [item for item in liquid if item["symbol"] in qualified_symbols]
        months_by_symbol = selected_months(monthly_path, qualified_symbols, timeframe, variant)
        records = []
        for item in candidates:
            months = sorted(months_by_symbol[item["symbol"]], key=lambda row: row["start"])
            recent = trailing_period(months, 12)
            records.append({**item, "trailing_12m_return_pct": recent["return_pct"],
                            "annual": calendar_years(months),
                            "late_positive_months": sum(
                                float(row["return_pct"]) > 0 for row in months
                                if row.get("sample") != "train"),
                            "late_months": sum(row.get("sample") != "train" for row in months),
                            "candle_quality": candle_quality(CACHE, item["symbol"], timeframe)})
        if len(records) != screening["passed_trailing_12m"]:
            raise RuntimeError(f"focused review differs from full-grid screening: {request}")
        assessment = ("NUMERIC_PASS_REVIEW_ONLY" if len(records) >= MIN_PAPER_STOCKS
                      else "NO_PASSING_STOCKS")
        reviews.append({"timeframe": timeframe, "variant": variant,
                        "train_rank": screening["train_rank"],
                        "qualified_count": len(records),
                        "assessment": assessment,
                        "stocks": records})
    return reviews


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def relative_link(path: Path, from_dir: Path) -> str:
    return os.path.relpath(path, from_dir)


def report_text(protocol_path: Path, results: Path, package: dict) -> str:
    protocol = package["protocol"]
    validation = package["validation"]
    rule = package.get("rule")
    activation = package.get("activation")
    decision = package.get("decision") or {}
    lines = ["# Кандидат и виртуальная проверка", "",
             f"Статус: **{activation['status'] if activation else package['status']}**. "
             + (f"Зарегистрировано виртуальных счетов: {len(activation.get('accounts', []))}; реальные заявки не создаются."
                if activation else "Создан из замороженных результатов; виртуальные счета пока не зарегистрированы."), "",
             f"[Протокол]({relative_link(protocol_path, results)}) · "
             "[общий отчёт](REPORT.md) · [все варианты](all_variants.csv) · "
             "[каждый месяц](monthly_returns.csv) · [проверка данных](validation.json) · "
             "[машинный пакет](paper_review.json)", "",
             "## Проверка входных данных", "",
             f"Структура: {'пройдена' if validation.get('structural_ok') else 'ошибка'}; "
             f"статус данных: `{validation.get('status')}`. "
             f"Пары с календарными пропусками: {validation.get('monthly_validation', {}).get('gap_pairs', '—')}; "
             f"затронутые акции × интервал: {validation.get('monthly_validation', {}).get('affected_symbol_timeframes', '—')}. "
             f"Корпоративные события: `{validation.get('corporate_actions', {}).get('status', 'unchecked')}`. "
             "Детали и примеры — в `validation.json`.", ""]
    if decision.get("status") == "CLOSED":
        lines += ["## Итоговое решение", "", str(decision.get("reason", "Исследование закрыто")),
                  "", "Допуск к paper trading не рассматривается; проверка возможных пропусков "
                  "свечей для этих кандидатов не требуется.", ""]
    if not rule:
        lines += ["## Решение", "", "Фиксированное правило не рекомендовано: "
                  + "; ".join(package["blockers"]) + ".", ""]
        return "\n".join(lines)
    annual_by_symbol = {symbol: calendar_years(months) for symbol, months in
                        selected_months(results / "monthly_returns.csv",
                                        {item["symbol"] for item in package["stocks"]},
                                        rule["timeframe"], rule["variant"]).items()}
    selected_rank = package.get("screening_summary", {}).get("selected_train_rank", 1)
    lines += ["## Выбор общей настройки", "",
              f"**{rule['variant']} · {rule['timeframe']}** на {rule['symbols']} акциях. "
              f"Ранг {selected_rank} по ранним месяцам; первая настройка в этом рейтинге, "
              "для которой хотя бы одна акция прошла годовой порог. "
              "Медианная доля прибыльных ранних месяцев "
              f"{rule['median_train_positive_share_pct']:.1f}%, средняя месячная доходность "
              f"{percent(rule['median_train_mean_month_return_pct'])}. Поздняя доля "
              f"{rule['median_late_positive_share_pct']:.1f}% и месячная доходность "
              f"{percent(rule['median_late_mean_month_return_pct'])} показаны отдельно; поздний отрезок уже был просмотрен.", "",
              "| Интервал · вариант | Акций | Ранние прибыльные месяцы | Ранняя средняя доходность | Поздние прибыльные месяцы | Поздняя средняя доходность |",
              "|---|---:|---:|---:|---:|---:|"]
    for item in package["candidate_rules"][:5]:
        lines.append(f"| {item['timeframe']} · `{item['variant']}` | {item['symbols']} | "
                     f"{item['median_train_positive_share_pct']:.1f}% | "
                     f"{percent(item['median_train_mean_month_return_pct'])} | "
                     f"{item['median_late_positive_share_pct']:.1f}% | "
                     f"{percent(item['median_late_mean_month_return_pct'])} |")
    screened = package.get("rule_screening", [])
    if screened:
        feasible = [item for item in screened if item["has_paper_candidates"]]
        other_feasible = len(feasible) - int(bool(package["stocks"]))
        costs_ready = str(protocol.get("cost_status", "")).startswith("after_")
        count_text = str(len(package["stocks"])) if costs_ready else "—"
        screening_note = (f"Просмотрены все {len(screened)} общие пары «интервал × вариант». "
                          + (f"После модельных расходов у выбранной настройки "
                             f"порог прошли {count_text} ликвидных акций; "
                             f"хотя бы одну прошедшую акцию дают ещё {other_feasible} настроек. "
                             "Эти альтернативы найдены на уже просмотренной истории и требуют "
                             "отдельного подтверждения перед заменой заранее выбранного правила."
                             if costs_ready else
                             "До пересчёта расходов порог >10% оценить нельзя; «—» не означает "
                             "нулевое число подходящих акций."))
        lines += ["", "## Проверка всех настроек по порогу paper", "",
                  screening_note, "",
                  "| Ранг по ранним месяцам | Интервал · вариант | Ликвидных акций >10% за последние 12 месяцев |",
                  "|---:|---|---:|"]
        highlights = screened[:1] + [item for item in feasible[:5] if item is not screened[0]]
        for item in highlights:
            passed_text = (str(item["passed_trailing_12m"])
                           if item["passed_trailing_12m"] is not None else "—")
            lines.append(f"| {item['train_rank']} | {item['timeframe']} · `{item['variant']}` | "
                         f"{passed_text} |")
        lines += ["", "[Результат для каждой настройки](paper_review.json) → `rule_screening`."]
    if package.get("focused_reviews"):
        lines += ["", "## Отдельное ревью запрошенных настроек", "",
                  "Это варианты, найденные после просмотра результатов. Они не заменяют "
                  "первичный выбор и не считаются независимым подтверждением. "
                  "Годы — отдельные календарные периоды; 2026 неполный. "
                  "Порог paper проверяется по последним полным 12 месяцам после модельных расходов. "
                  "Официально объявленные остановки торгов не считаются пропусками свечей: "
                  "[13.02.2024](https://www.moex.com/n67524?nt=0), "
                  "[13.09.2025](https://www.moex.com/n93603).", ""]
        for focus in package["focused_reviews"]:
            records = focus["stocks"]
            lines += [f"### {focus['timeframe']} · `{focus['variant']}`", "",
                      f"Ранг по ранним месяцам: {focus['train_rank']}; "
                      f"порог прошли {focus['qualified_count']} ликвидных акций. "
                      f"Кандидаты: все {len(records)} прошедших акций. "
                      f"Итог проверки: **{focus['assessment']}**. "
                      "Для запуска ещё нужны проверка корпоративных событий, "
                      "фиксированная исполняемая реализация и сверка её сигналов с расчётом. "
                      "Поздний период уже использован для поиска этой настройки; "
                      "он не подтверждает результат независимо.", "",
                      "| Акция | Последние 12м | 2024 | 2025 | 2026 YTD | Поздние месяцы + | Макс. просадка | Свечи |",
                      "|---|---:|---:|---:|---:|---:|---:|---|"]
            for item in records:
                annual = {year["year"]: year["return_pct"] for year in item["annual"]}
                quality = item["candle_quality"]
                label = item["symbol"]
                lines.append(f"| {label} | {percent(item['trailing_12m_return_pct'])} | "
                             f"{percent(annual.get('2024'))} | {percent(annual.get('2025'))} | "
                             f"{percent(annual.get('2026'))} | "
                             f"{item['late_positive_months']}/{item['late_months']} | "
                             f"{percent(item['max_drawdown_pct'])} | "
                             f"{quality['status']} "
                             f"(остановки MOEX: {quality.get('documented_market_halt_hours', 0)}) |")
            lines.append("")
    liquidity = package["liquidity"]
    lines += ["", "## Акции первично выбранной настройки", "",
              f"Оборот: медиана `close × volume` за последние 60 дневных свечей; "
              f"порог верхней четверти среди {liquidity['measured_liquidity']} измеренных акций — "
              f"{liquidity['turnover_threshold_rub']:,.0f} ₽. Параметры правила для всех акций одинаковы. "
              "Акции ранжированы только по ранним месяцам; поздние результаты приведены для проверки.", "",
              "| Акция | Ранние месяцы + | Поздние месяцы + | Средний ранний / поздний месяц | Последний календарный год / YTD | Худший месяц рано / поздно | Сделки | Макс. просадка | Оборот 60д |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in package["stocks"]:
        latest = annual_by_symbol[item["symbol"]][-1]
        annual_label = latest["year"] + ("" if latest["complete"] else " YTD")
        lines.append(f"| {item['symbol']} | {item['train_positive_share_pct']:.1f}% "
                     f"({item['train_months']}) | {item['late_positive_share_pct']:.1f}% "
                     f"({item['late_months']}) | {percent(item['train_mean_month_return_pct'])} / "
                     f"{percent(item['late_mean_month_return_pct'])} | {annual_label}: "
                     f"{percent(latest['return_pct'])} · {latest['pnl_rub']:,.0f} ₽ | "
                     f"{item['train_worst_month_pnl_rub']:,.0f} / {item['late_worst_month_pnl_rub']:,.0f} ₽ | "
                     f"{item['closed_trades']} | {percent(item['max_drawdown_pct'])} | "
                     f"{item['turnover_60d_rub']:,.0f} ₽ |")
    lines += ["", "### PnL по календарным годам", "",
              "Один непрерывный счёт; неполный год помечен YTD и включает только завершённые месяцы.", "",
              "| Акция | Год | Месяцев | PnL | Доходность |",
              "|---|---|---:|---:|---:|"]
    for item in package["stocks"]:
        for annual in annual_by_symbol[item["symbol"]]:
            year = annual["year"] + ("" if annual["complete"] else " YTD")
            lines.append(f"| {item['symbol']} | {year} | {annual['months']} | "
                         f"{annual['pnl_rub']:,.0f} ₽ | {percent(annual['return_pct'])} |")
    lines += ["", "### Последние полные периоды", "",
              "Накопленная доходность по непрерывному счёту; «—» означает, что полного непрерывного окна нет.", "",
              "| Акция | 1 месяц | 3 месяца | 6 месяцев | 9 месяцев | 12 месяцев |",
              "|---|---:|---:|---:|---:|---:|"]
    for item in package["stocks"]:
        cells = [percent(item["recent_periods"][str(n)]["return_pct"] if item["recent_periods"][str(n)] else None)
                 for n in PERIODS]
        lines.append("| " + " | ".join([item["symbol"], *cells]) + " |")
    lines += ["", "### Каждый полный месяц", "",
              "🟩 плюс, 🟥 минус, ⬜ ноль; «—» нет полного месяца. Поздние месяцы уже просмотрены.", "",
              "| Акция | Год | Янв | Фев | Мар | Апр | Май | Июн | Июл | Авг | Сен | Окт | Ноя | Дек |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for item in package["stocks"]:
        years = defaultdict(dict)
        for month in item["months"]:
            year, number = month["month"].split("-")
            years[year][int(number)] = month["return_pct"]
        for year, months in sorted(years.items()):
            cells = []
            for number in range(1, 13):
                value = months.get(number)
                marker = "🟩" if value is not None and value > 0 else "🟥" if value is not None and value < 0 else "⬜"
                cells.append(f"{marker} {percent(value)}" if value is not None else "—")
            lines.append("| " + " | ".join([item["symbol"], year, *cells]) + " |")
    if decision.get("status") == "CLOSED":
        return "\n".join(lines + ["", "Эксперимент закрыт; виртуальные счета по нему не создаются.", ""])
    lines += ["", "## Готовность к paper trading", "",
              f"Историческая модель расходов: `{protocol.get('cost_status', 'не указана')}`. "
              f"Размер позиции в бэктесте: {protocol.get('position_weight_pct', '—')}% "
              f"от отдельного счёта {protocol.get('initial_capital_rub', '—')} ₽. "
              "Лоты, фактическое проскальзывание, стоимость займа short и дивиденды требуют отдельной сверки.", "",
              "Ограничения и открытые проверки:", ""]
    lines += [f"- {blocker}" for blocker in package["blockers"]]
    if activation:
        lines += ["", f"Виртуальная стратегия: `{activation['strategy_id']}`; "
                  f"зарегистрировано {len(activation['accounts'])} отдельных счетов. "
                  "Их фактический запуск проверяется по `papertrading/live/LIFECYCLE.json`. "
                  "Pine в TradingView ещё требует ручной сверки сделок. Реальная торговля не разрешена.", ""]
    else:
        lines += ["", "Для виртуального подключения нужны фиксированные Python/Pine, проверка сигналов "
                  "и конфигурация для каждой прошедшей акции. Реальная торговля не разрешена.", ""]
    return "\n".join(lines)


def prepare(protocol_path: Path, results: Path, focus_rules: list[str] | None = None) -> dict:
    protocol_path = protocol_path.resolve()
    results = results.resolve()
    command = [sys.executable, str(ROOT / "skills/new-experiment/scripts/validate_run.py"),
               "--protocol", str(protocol_path), "--results", str(results)]
    completed = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError("validation failed: " + completed.stderr[-2000:])
    validation_path = results / "validation.json"
    if not validation_path.exists():
        raise RuntimeError("validation did not produce validation.json")
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    previous_review_path = results / "paper_review.json"
    previous_review = (json.loads(previous_review_path.read_text(encoding="utf-8"))
                       if previous_review_path.is_file() else {})
    focus_rules = focus_rules if focus_rules is not None else previous_review.get("focus_rules", [])
    decision_path = results / "decision.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8")) if decision_path.is_file() else {}
    if decision.get("status") == "CLOSED":
        review_path = results / "paper_review.json"
        previous = json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else {}
        package = {**previous, "status": "CLOSED", "protocol": protocol,
                   "validation": validation, "decision": decision,
                   "rule": None, "candidate_rules": [], "stocks": [],
                   "blockers": [str(decision.get("reason") or "Исследование закрыто")]}
        review_path.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (results / "PAPER_REVIEW.md").write_text(
            report_text(protocol_path, results, package), encoding="utf-8")
        return package
    package = {"review_version": 2, "selection_scope": "all_passing",
               "selection_method": "first_train_rank_with_passing_stocks",
               "status": "REVIEW_ONLY", "protocol": protocol, "validation": validation,
               "focus_rules": focus_rules,
               "rule": None, "candidate_rules": [], "stocks": [], "blockers": []}
    if not validation.get("structural_ok"):
        package["status"] = "INVALID_DATA"
        package["blockers"].append("структурная проверка данных не пройдена")
    else:
        metrics = monthly_metrics(results / "monthly_returns.csv")
        prefixes = tuple(protocol.get("promotion_variant_prefixes") or ())
        if any(not isinstance(prefix, str) or not prefix for prefix in prefixes):
            raise ValueError("promotion_variant_prefixes must contain nonempty strings")
        rule, candidates = choose_global_rule(metrics, variant_prefixes=prefixes)
        package["candidate_rules"] = candidates
        if rule is None:
            package["blockers"].append("нет варианта с минимум 100 акциями, тремя ранними и одним поздним месяцем")
        else:
            rows = read_csv(results / "all_variants.csv")
            result_rows = {(row["symbol"], row["timeframe"], row["variant"]): row for row in rows}
            package["rule_screening"] = screen_every_rule(
                candidates, metrics, result_rows, results / "monthly_returns.csv",
                protocol.get("cost_status", ""))
            passing_rule, chosen_screen = first_passing_rule(candidates, package["rule_screening"])
            if passing_rule is not None:
                rule = passing_rule
            package["rule"] = rule
            package["screening_summary"] = {
                "rules_checked": len(package["rule_screening"]),
                "rules_with_paper_candidates": sum(item["has_paper_candidates"]
                                                   for item in package["rule_screening"]),
                "selected_train_rank": chosen_screen["train_rank"] if chosen_screen else 1,
                "selected_passed": (chosen_screen or package["rule_screening"][0])["passed_trailing_12m"],
                "max_passed_any_rule": (max(item["passed_trailing_12m"]
                                            for item in package["rule_screening"])
                                        if protocol.get("cost_status", "").startswith("after_") else None),
            }
            package["focused_reviews"] = review_focused_rules(
                focus_rules, package["rule_screening"], metrics, result_rows,
                results / "monthly_returns.csv")
            candidates_for_paper, liquidity = select_stocks(rule, metrics, result_rows, limit=None)
            package["liquidity"] = liquidity
            selected = selected_months(results / "monthly_returns.csv",
                                       {item["symbol"] for item in candidates_for_paper},
                                       rule["timeframe"], rule["variant"])
            qualified = []
            threshold = POLICY["min_trailing_12m_return_pct_after_costs"]
            for item in candidates_for_paper:
                months = sorted(selected[item["symbol"]], key=lambda row: row["start"])
                item["recent_periods"] = {str(n): trailing_period(months, n) for n in PERIODS}
                last_year = item["recent_periods"].get("12") or {}
                if (not protocol.get("cost_status", "").startswith("after_")
                        or last_year.get("return_pct") is None
                        or last_year["return_pct"] <= threshold):
                    continue
                item["months"] = [{"month": month["start"][:7],
                                   "return_pct": round(float(month["return_pct"]), 2),
                                   "closed_trades": int(month["closed_trades"])} for month in months]
                qualified.append(item)
            stocks = qualified
            for item in stocks:
                item["candle_quality"] = candle_quality(CACHE, item["symbol"], rule["timeframe"])
            package["screening"] = {"liquid_candidates": len(candidates_for_paper),
                                    "passed_trailing_12m": len(qualified),
                                    "threshold_after_costs_pct": threshold}
            if (protocol.get("cost_status", "").startswith("after_")
                    and len(qualified) != package["screening_summary"]["selected_passed"]):
                raise RuntimeError("screening mismatch for the selected rule")
            package["stocks"] = stocks
            if len(stocks) < MIN_PAPER_STOCKS and protocol.get("cost_status", "").startswith("after_"):
                package["blockers"].append(
                    f"для выбранной настройки найдено {len(stocks)} акций с полными "
                    f"12 месяцами и доходностью >{threshold:g}% после расходов; "
                    f"по всей сетке хотя бы одну прошедшую акцию дают "
                    f"{package['screening_summary']['rules_with_paper_candidates']} настроек")
            if validation.get("monthly_validation", {}).get("gap_pairs", 0):
                package["blockers"].append("в исходной выборке есть календарные пропуски; проверь затронутые пары")
            if validation.get("corporate_actions", {}).get("status") != "complete":
                package["blockers"].append("дивиденды и сплиты покрыты не полностью")
            if protocol.get("cost_status") == "gross_before_costs":
                package["blockers"].append("расчёт до расходов; пересчитай выбранное правило после расходов")
            package["blockers"].append("Python/Pine реализация и совпадение сигналов для выбранного правила не проверены")
            package["blockers"].append("фактические лоты, заём short и конфигурации paper-счетов не проверены")
    (results / "paper_review.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (results / "PAPER_REVIEW.md").write_text(report_text(protocol_path, results, package), encoding="utf-8")
    return package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--focus", action="append", dest="focus_rules",
                        help="timeframe:variant for a separate post-hoc review; repeatable")
    args = parser.parse_args()
    package = prepare(args.protocol, args.results, focus_rules=args.focus_rules)
    print(json.dumps({"status": package["status"], "rule": package["rule"],
                      "stocks": [item["symbol"] for item in package["stocks"]],
                      "blockers": package["blockers"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if package["status"] in ("REVIEW_ONLY", "CLOSED") else 1)


if __name__ == "__main__":
    main()
