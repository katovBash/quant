"""Summarize staged EMA pattern scan without hiding failed or inactive variants."""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from src.ema.core.research_ema_combinations import CANDIDATES, ROOT

OUT = ROOT / "execute"


def number(row: dict, key: str) -> float:
    return float(row[key])


def win_rate(row: dict, prefix: str) -> float:
    trades = int(row[prefix + "closed_trades"])
    return 100 * int(row[prefix + "winning_trades"]) / trades if trades else 0.0


def main() -> None:
    rows = list(csv.DictReader((OUT / "all_results.csv").open(encoding="utf-8")))
    baselines = {(r["symbol"], r["timeframe"]): r for r in rows if r["variant"] == "baseline"}
    others = [r for r in rows if r["variant"] != "baseline"]
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    by_variant: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_symbol[row["symbol"]].append(row)
        if row["variant"] != "baseline":
            by_variant[row["variant"]].append(row)
    errors = json.loads((OUT / "errors.json").read_text())
    report = ["# EMA12/33: поэтапное сравнение индикаторов и паттернов", "",
              f"{len(baselines)} пар символ/интервал, {len(by_symbol)} символов, {len(by_variant)} дополнительных комбинаций, {len(errors)} ошибок чтения. Кэш MOEX ISS до 30.10.2026. Контроль — EMA12/33 long+short с теми же капиталом, комиссией, тиком и исполнением на следующем баре. История развития: до 01.01.2025; поздняя проверка: с 01.01.2025. Для 1H/4H период развития начинается в 2024 году.", "",
              "## Правила семи добавок", "",
              "| Подход | Формальное правило на закрытии EMA-сигнала |",
              "| --- | --- |",
              "| `breakout20` | За последние 5 свечей было закрытие выше максимума предыдущих 20 свечей для long или ниже минимума для short. |",
              "| `engulfing` | За последние 3 свечи было тело бычьего/медвежьего поглощения противоположной предыдущей свечи. |",
              "| `hammer` | За последние 3 свечи был бычий молот / медвежья падающая звезда: соответствующая тень ≥2 тела, другая ≤1 тела. |",
              "| `double_pattern` | Два подтверждённых 3/3 минимума/максимума на расстоянии 8–80 свечей с различием ≤3%; расстояние до «шеи» ≥3%; закрытие пробило шею не раньше подтверждения второго экстремума и не более 10 свечей назад. |",
              "| `volume` | За последние 3 свечи объём превысил 1,5 среднего объёма предыдущих 20 свечей. |",
              "| `range_expansion` | За последние 3 свечи истинный диапазон превысил 1,5 среднего диапазона предыдущих 20 свечей. |",
              "| `adx20` | ADX14 ≥20 на свече пересечения. |",
              "", "Все добавки разрешают или отклоняют **новый вход только при пересечении EMA**. Встречный EMA-сигнал всегда закрывает открытую позицию. Комбинация — логическое И условий. Базовая EMA считается одним подходом; потому «2 подхода» = EMA + 1 добавка, «5 подходов» = EMA + 4 добавки. Параметры зафиксированы до скана.", "",
              "## Этапы и активность", "",
              "В таблице ниже знаменатель — пары, где базовая стратегия имеет ≥1 закрытой сделки в позднем периоде. Улучшение означает большую позднюю доходность, **не** доказанную будущую прибыль. Вариант без поздних сделок считается неактивным.", "",
              "| Таймфрейм | Подходов | Вариантов | Сравнений | Улучшили позднюю доходность | Без сделок | Медиана Δ, п.п. | Медиана сделок / win rate / PF среди ≥3 сделок |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for timeframe in ("1D", "1W", "1M", "1H", "4H"):
        for approaches in range(2, 6):
            sample = [r for r in others if r["timeframe"] == timeframe and int(r["approaches"]) == approaches
                      and int(baselines[(r["symbol"], timeframe)]["late_closed_trades"]) >= 1]
            deltas = [number(r, "late_return_pct") - number(baselines[(r["symbol"], timeframe)], "late_return_pct") for r in sample]
            active = [r for r in sample if int(r["late_closed_trades"]) >= 3]
            median_trades = statistics.median(int(r["late_closed_trades"]) for r in active) if active else 0
            median_win = statistics.median(win_rate(r, "late_") for r in active) if active else 0
            finite_pf = [number(r, "late_profit_factor") for r in active if r["late_profit_factor"] != "inf"]
            median_pf = statistics.median(finite_pf) if finite_pf else 0
            report.append(f"| {timeframe} | {approaches} | {len({r['variant'] for r in sample})} | {len(sample)} | {sum(d > 0 for d in deltas)} | {sum(int(r['late_closed_trades']) == 0 for r in sample)} | {statistics.median(deltas) if deltas else 0:+.2f} | {median_trades:.1f} / {median_win:.1f}% / {median_pf:.2f} |")

    summary = []
    for variant, variant_rows in by_variant.items():
        eligible = [r for r in variant_rows if r["timeframe"] in ("1D", "4H")
                    and number(r, "train_daily_turnover_rub") >= 50_000_000
                    and int(baselines[(r["symbol"], r["timeframe"])]["late_closed_trades"]) >= 3]
        both_improved = [r for r in eligible if
                         number(r, "train_return_pct") > number(baselines[(r["symbol"], r["timeframe"])], "train_return_pct")
                         and number(r, "late_return_pct") > number(baselines[(r["symbol"], r["timeframe"])], "late_return_pct")
                         and int(r["train_closed_trades"]) >= 5 and int(r["late_closed_trades"]) >= 3]
        summary.append({"variant": variant, "approaches": len(variant.split("+")) + 1,
                        "eligible_pairs": len(eligible), "both_improved_pairs": len(both_improved),
                        "late_active_pairs": sum(int(r["late_closed_trades"]) >= 3 for r in eligible),
                        "median_late_trades_active": round(statistics.median(
                            int(r["late_closed_trades"]) for r in eligible if int(r["late_closed_trades"]) >= 3), 1)
                            if any(int(r["late_closed_trades"]) >= 3 for r in eligible) else 0,
                        "median_late_win_rate_active": round(statistics.median(
                            win_rate(r, "late_") for r in eligible if int(r["late_closed_trades"]) >= 3), 1)
                            if any(int(r["late_closed_trades"]) >= 3 for r in eligible) else 0,
                        "median_late_delta_pp": round(statistics.median(
                            number(r, "late_return_pct") - number(baselines[(r["symbol"], r["timeframe"])], "late_return_pct")
                            for r in eligible), 2) if eligible else 0.0})
    summary.sort(key=lambda r: (r["approaches"], -r["both_improved_pairs"], -r["median_late_delta_pp"]))
    with (OUT / "variant_summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    report += ["", "На 1W и особенно 1M положительная медиана часто возникает потому, что фильтр **не совершил сделок**, пока базовая EMA теряла деньги. Такие строки не считаются рабочей стратегией; смотрите столбцы активности и числа сделок.", "",
               "## Варианты с наибольшим числом улучшений в обоих периодах", "",
               "Счёт ведётся только среди ликвидных 1D/4H пар с минимумом сделок; он не учитывает величину улучшения и служит ориентиром для просмотра, не рейтингом доходности.", "",
               "| Подходов | Вариант | Улучшили оба периода / допустимые пары | Поздние ≥3 сделки | Медиана позднего Δ |",
               "| ---: | --- | ---: | ---: | ---: |"]
    for row in sorted(summary, key=lambda r: (-r["both_improved_pairs"], r["approaches"], -r["median_late_delta_pp"]))[:20]:
        report.append(f"| {row['approaches']} | `{row['variant']}` | {row['both_improved_pairs']}/{row['eligible_pairs']} | {row['late_active_pairs']} | {row['median_late_delta_pp']:+.2f} п.п. |")

    selected = []
    for row in others:
        if row["timeframe"] not in ("1D", "4H") or number(row, "train_daily_turnover_rub") < 50_000_000:
            continue
        baseline = baselines[(row["symbol"], row["timeframe"])]
        minimum_train = 5 if row["timeframe"] == "1D" else 10
        minimum_late = 3 if row["timeframe"] == "1D" else 8
        if (int(row["train_closed_trades"]) < minimum_train or
                int(row["late_closed_trades"]) < minimum_late or
                int(row["late_winning_trades"]) < 1 or
                number(row, "train_return_pct") <= max(0, number(baseline, "train_return_pct")) or
                number(row, "late_return_pct") <= max(0, number(baseline, "late_return_pct")) or
                number(row, "late_max_drawdown_pct") < number(baseline, "late_max_drawdown_pct") - 2 or
                float(row["late_profit_factor"]) <= 1):
            continue
        selected.append(row | {
            "train_delta_pp": round(number(row, "train_return_pct") - number(baseline, "train_return_pct"), 2),
            "late_delta_pp": round(number(row, "late_return_pct") - number(baseline, "late_return_pct"), 2),
            "baseline_late_return_pct": baseline["late_return_pct"],
            "baseline_late_max_drawdown_pct": baseline["late_max_drawdown_pct"]})
    selected.sort(key=lambda r: (int(r["approaches"]), -number(r, "late_delta_pp")))
    success = ROOT / "success"
    success.mkdir(parents=True, exist_ok=True)
    with (success / "selected.csv").open("w", newline="", encoding="utf-8") as file:
        fields = list(selected[0]) if selected else list(rows[0]) + ["train_delta_pp", "late_delta_pp", "baseline_late_return_pct", "baseline_late_max_drawdown_pct"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    success_lines = ["# Исторические кандидаты комбинирования", "",
                     f"Всего строк, прошедших формальные критерии: {len(selected)}. Отбор по известным данным после проверки 98 комбинаций; это сильный источник подгонки. Для paper trading нужны заранее зафиксированные правила и новые сделки.", "",
                     "Критерии: 1D/4H, медианный дневной оборот до 2025 года ≥50 млн ₽; ≥5/10 сделок до 2025 и ≥3/8 после для 1D/4H; хотя бы одна поздняя прибыльная; положительная доходность и превосходство базы в обоих периодах; поздняя просадка не глубже базы более чем на 2 п.п.; поздний PF >1.", "",
                     "| Символ | Интервал | Подходов | Добавки | Поздняя доходность / база | Улучшение | Сделки / прибыльные | Win rate | PF | Просадка |",
                     "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in selected[:40]:
        symbol = row["symbol"]
        success_lines.append(f"| [{symbol}](../tickers/{symbol}/README.md) | {row['timeframe']} | {row['approaches']} | `{row['variant']}` | {number(row, 'late_return_pct'):+.2f}% / {number(row, 'baseline_late_return_pct'):+.2f}% | {number(row, 'late_delta_pp'):+.2f} п.п. | {row['late_closed_trades']} / {row['late_winning_trades']} | {win_rate(row, 'late_'):.1f}% | {row['late_profit_factor']} | {number(row, 'late_max_drawdown_pct'):.2f}% |")
    success_lines += ["", "[Полный список](selected.csv), [все результаты без отбора](../execute/all_results.csv). Число строк в таблице ограничено 40 ради читаемости; CSV полный."]
    (success / "README.md").write_text("\n".join(success_lines) + "\n")
    high_win = [r for r in others if r["timeframe"] in ("1D", "4H")
                and number(r, "train_daily_turnover_rub") >= 50_000_000
                and int(r["train_closed_trades"]) >= (5 if r["timeframe"] == "1D" else 10)
                and int(r["late_closed_trades"]) >= (8 if r["timeframe"] == "1D" else 20)
                and win_rate(r, "late_") >= 60
                and number(r, "late_return_pct") > 0 and float(r["late_profit_factor"]) > 1]
    high_win.sort(key=lambda r: (int(r["approaches"]), -win_rate(r, "late_"), -number(r, "late_return_pct")))
    with (success / "high_win_rate.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(high_win)
    high_win_lines = ["# Высокий win rate при достаточном числе сделок", "",
                      f"Найдено {len(high_win)} исторических строк: 1D ≥8 или 4H ≥20 поздних закрытых сделок, поздний win rate ≥60%, поздняя доходность >0 и PF >1 после моделируемых издержек. **Ранний win rate здесь не фильтруется**, а показан рядом: так видно, когда высокий процент появился лишь позже. Это отдельная линза, не автоматический выбор. Отбор после перебора 98 комбинаций сильно смещён.", "",
                      "| Символ | Интервал | Добавки | Ранняя / поздняя доходность | Ранний / поздний win rate | Поздние сделки / прибыльные | PF | Просадка |",
                      "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in high_win[:40]:
        high_win_lines.append(f"| [{row['symbol']}](../tickers/{row['symbol']}/README.md) | {row['timeframe']} | `{row['variant']}` | {number(row, 'train_return_pct'):+.2f}% / {number(row, 'late_return_pct'):+.2f}% | {win_rate(row, 'train_'):.1f}% / {win_rate(row, 'late_'):.1f}% | {row['late_closed_trades']} / {row['late_winning_trades']} | {row['late_profit_factor']} | {number(row, 'late_max_drawdown_pct'):.2f}% |")
    high_win_lines += ["", "[Полная таблица](high_win_rate.csv). Если список пуст, критерий не выполнен; не снижайте требуемое число сделок ради красивого процента."]
    (success / "HIGH_WIN_RATE.md").write_text("\n".join(high_win_lines) + "\n")
    ticker_root = ROOT / "tickers"
    ticker_root.mkdir(parents=True, exist_ok=True)
    (ticker_root / "README.md").write_text(f"# Символы исследования\n\n{len(by_symbol)} символов; у каждого `<ТИКЕР>/README.md` есть базовые показатели и лучшие исторические комбинации по доступным интервалам. [Полный CSV](../execute/all_results.csv).\n")
    for symbol, ticker_rows in by_symbol.items():
        page = [f"# {symbol} · EMA12/33 и дополнительные подходы", "",
                "Кэш MOEX ISS; поздний период начинается 01.01.2025. В таблице базовая EMA, до трёх лучших по поздней доходности и до двух лучших по позднему win rate при минимум 3 закрытых сделках. Такие строки отобраны **после просмотра истории**; полный CSV сохраняет остальные варианты.", "",
                "| Интервал | Роль | Добавки | Подходов | Ранняя / поздняя доходность | Поздние сделки / прибыльные | Win rate | PF | Поздняя просадка |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for timeframe in ("1D", "1W", "1M", "1H", "4H"):
            key = (symbol, timeframe)
            if key not in baselines:
                continue
            base = baselines[key]
            page.append(f"| {timeframe} | Контроль | **Чистая EMA12/33** | 1 | {number(base, 'train_return_pct'):+.2f}% / {number(base, 'late_return_pct'):+.2f}% | {base['late_closed_trades']} / {base['late_winning_trades']} | {win_rate(base, 'late_'):.1f}% | {base['late_profit_factor']} | {number(base, 'late_max_drawdown_pct'):.2f}% |")
            choices = [r for r in ticker_rows if r["timeframe"] == timeframe and r["variant"] != "baseline"
                       and int(r["late_closed_trades"]) >= 3]
            choices.sort(key=lambda r: (number(r, "late_return_pct"), -int(r["approaches"])), reverse=True)
            top_returns = choices[:3]
            top_wins = sorted(choices, key=lambda r: (win_rate(r, "late_"), int(r["late_closed_trades"])), reverse=True)[:2]
            chosen = {r["variant"]: (r, "Доходность") for r in top_returns}
            for row in top_wins:
                chosen.setdefault(row["variant"], (row, "Win rate"))
            for row, role in chosen.values():
                page.append(f"| {timeframe} | {role} | `{row['variant']}` | {row['approaches']} | {number(row, 'train_return_pct'):+.2f}% / {number(row, 'late_return_pct'):+.2f}% | {row['late_closed_trades']} / {row['late_winning_trades']} | {win_rate(row, 'late_'):.1f}% | {row['late_profit_factor']} | {number(row, 'late_max_drawdown_pct'):.2f}% |")
        page += ["", "[Все варианты и метрики](../../execute/all_results.csv). Лучшие прошлые строки выбраны после просмотра данных и не являются прогнозом."]
        folder = ticker_root / symbol
        folder.mkdir(exist_ok=True)
        (folder / "README.md").write_text("\n".join(page) + "\n")
    counts = {stage: sum(int(row["approaches"]) == stage for row in selected) for stage in range(2, 6)}
    report += ["", "## Что прошло строгий исторический отбор", "",
               f"2 подхода: **{counts[2]}** строк; 3 подхода: **{counts[3]}**; 4 подхода: **{counts[4]}**; 5 подходов: **{counts[5]}**. Варианты с двойным дном/вершиной не прошли критерии достаточного числа сделок и улучшения в обоих периодах. Более сложные сочетания здесь не дают основания заменять простые правила.", "",
               "## Ограничения и следующий шаг", "",
               "Открытая позиция входит в доходность и просадку, но не в число закрытых сделок. Short не включает стоимость займа и дивидендные обязательства. 4H агрегирован из часовых свечей. Статистика вариантов не сверена с Pine Strategy Tester. После выбора по нескольким вариантам поздний период тоже перестаёт быть нетронутой выборкой; реальная следующая проверка — новые бумажные сделки с зафиксированным кодом.", "",
               "[Все строки](all_results.csv) · [сводка вариантов](variant_summary.csv) · [отбор по доходности](../success/README.md) · [отбор по win rate](../success/HIGH_WIN_RATE.md) · [ошибки](errors.json)."]
    (OUT / "RESEARCH.md").write_text("\n".join(report) + "\n")
    print(f"report: selected={len(selected)}; variants={len(by_variant)}; symbols={len(by_symbol)}")


if __name__ == "__main__":
    main()
