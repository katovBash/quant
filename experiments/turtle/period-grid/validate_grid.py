"""Time-ordered Turtle selection, neighboring parameters, and cost stress."""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from signals import prior_extrema, turtle_from_extrema
from src.ema.core.research_ema_combinations import simulate
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
PROTOCOL = json.loads((HERE / "protocol.json").read_text())
PLAN = PROTOCOL["walk_forward"]
CACHE = ROOT / "data/candles/moex_scan"
REF = ("dennis_turtle_20_10", "dennis_turtle_55_20")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def median(values: list[float]) -> float:
    return round(statistics.median(values), 4)


def summaries(group: dict[tuple[str, str, str], list[tuple[str, float, float]]],
              frame: str, variant: str, symbols: list[str], start: str, end: str,
              required: int) -> dict:
    shares, mean_returns, worsts, totals = [], [], [], []
    for symbol in symbols:
        months = [(pnl, ret) for date, pnl, ret in group[frame, variant, symbol]
                  if start <= date < end]
        if len(months) != required:
            continue
        shares.append(100 * sum(pnl > 0 for pnl, _ in months) / required)
        mean_returns.append(statistics.mean(ret for _, ret in months))
        worsts.append(min(pnl for pnl, _ in months))
        totals.append(sum(pnl for pnl, _ in months))
    return {"symbols": len(shares),
            "median_positive_month_share_pct": median(shares) if shares else None,
            "median_mean_month_return_pct": median(mean_returns) if shares else None,
            "median_worst_month_pnl_rub": median(worsts) if shares else None,
            "median_period_pnl_rub": median(totals) if shares else None,
            "positive_period_symbols": sum(value > 0 for value in totals)}


def variants_near(variant: str, variants: list[str]) -> list[str]:
    _, _, a, b = variant.split("_")
    a, b = int(a), int(b)
    entry = PROTOCOL["entry_lengths"]
    exit_lengths = PROTOCOL["exit_lengths"]
    result = []
    for other in variants:
        if other == "baseline" or other == variant:
            continue
        _, _, x, y = other.split("_")
        x, y = int(x), int(y)
        adjacent_entry = (y == b and abs(entry.index(x) - entry.index(a)) == 1)
        adjacent_exit = (x == a and abs(exit_lengths.index(y) - exit_lengths.index(b)) == 1)
        if adjacent_entry or adjacent_exit:
            result.append(other)
    return result


def main() -> None:
    with (OUT / "monthly_returns.csv").open(newline="", encoding="utf-8") as stream:
        monthly = defaultdict(list)
        for row in csv.DictReader(stream):
            monthly[row["timeframe"], row["variant"], row["symbol"]].append(
                (row["start"], float(row["pnl_rub"]), float(row["return_pct"])))
    with (OUT / "all_variants.csv").open(newline="", encoding="utf-8") as stream:
        pairs = list(csv.DictReader(stream))
    variants = sorted({row["variant"] for row in pairs})
    symbols_by_frame = {frame: sorted({row["symbol"] for row in pairs if row["timeframe"] == frame})
                        for frame in PROTOCOL["signal_timeframes"]}
    wf_rows = []
    selected = {}
    train_sets = {}
    stress_symbols = {}
    for frame in PROTOCOL["signal_timeframes"]:
        all_symbols = symbols_by_frame[frame]
        for fold in PLAN["folds"]:
            train = [symbol for symbol in all_symbols
                     if len([date for date, _, _ in monthly[frame, "baseline", symbol]
                             if fold["train_start"] <= date < fold["train_end"]]) == fold["train_months"]]
            train_sets[frame, fold["name"]] = train
            complete_test = [symbol for symbol in train
                             if len([date for date, _, _ in monthly[frame, "baseline", symbol]
                                     if fold["test_start"] <= date < fold["test_end"]]) == fold["test_months"]]
            if fold["name"] == "2026_ytd":
                stress_symbols[frame] = complete_test
            for variant in variants:
                training = summaries(monthly, frame, variant, train,
                                     fold["train_start"], fold["train_end"], fold["train_months"])
                testing = summaries(monthly, frame, variant, complete_test,
                                    fold["test_start"], fold["test_end"], fold["test_months"])
                wf_rows.append({"fold": fold["name"], "timeframe": frame, "variant": variant,
                                "train_start": fold["train_start"], "train_end": fold["train_end"],
                                "test_start": fold["test_start"], "test_end": fold["test_end"],
                                **{"train_" + k: v for k, v in training.items()},
                                **{"test_" + k: v for k, v in testing.items()},
                                "test_missing_symbols": len(train) - len(complete_test)})
            candidate_rows = [row for row in wf_rows if row["fold"] == fold["name"]
                              and row["timeframe"] == frame and row["variant"] != "baseline"]
            winner = max(candidate_rows, key=lambda row: (
                row["train_median_positive_month_share_pct"],
                row["train_median_mean_month_return_pct"],
                row["train_median_worst_month_pnl_rub"]))
            selected[frame, fold["name"]] = winner["variant"]
    write_csv(OUT / "walk_forward.csv", wf_rows)
    neighbor_rows = []
    for (frame, fold), variant in selected.items():
        base = next(row for row in wf_rows if row["timeframe"] == frame and row["fold"] == fold
                    and row["variant"] == variant)
        for neighbor in variants_near(variant, variants):
            row = next(row for row in wf_rows if row["timeframe"] == frame and row["fold"] == fold
                       and row["variant"] == neighbor)
            neighbor_rows.append({"fold": fold, "timeframe": frame,
                                  "selected_variant": variant, "neighbor_variant": neighbor,
                                  "train_selected_positive_share_pct": base["train_median_positive_month_share_pct"],
                                  "train_neighbor_positive_share_pct": row["train_median_positive_month_share_pct"],
                                  "test_selected_positive_share_pct": base["test_median_positive_month_share_pct"],
                                  "test_neighbor_positive_share_pct": row["test_median_positive_month_share_pct"],
                                  "test_selected_median_pnl_rub": base["test_median_period_pnl_rub"],
                                  "test_neighbor_median_pnl_rub": row["test_median_period_pnl_rub"]})
    write_csv(OUT / "neighbor_stability.csv", neighbor_rows)
    with (OUT / "monthly_case_summary.csv").open(newline="", encoding="utf-8") as stream:
        case = {(row["symbol"], row["timeframe"], row["variant"]): row
                for row in csv.DictReader(stream)}
    stress_rows = []
    for frame in PROTOCOL["signal_timeframes"]:
        variants_to_stress = sorted(set(REF) | {selected[frame, fold["name"]]
                                                for fold in PLAN["folds"]})
        for count, symbol in enumerate(stress_symbols[frame], 1):
            bars = load_research_bars(CACHE, symbol, frame)
            extrema = prior_extrema(bars, set(PROTOCOL["entry_lengths"] + PROTOCOL["exit_lengths"]))
            gate = [True] * len(bars)
            for variant in variants_to_stress:
                entry, exit_length = (int(value) for value in variant.split("_")[-2:])
                signals, exits = turtle_from_extrema(bars, entry, exit_length, extrema)
                for cost in PLAN["cost_stress_bps_per_side"]:
                    if cost == PROTOCOL["simulator_cost_bps_per_side"]:
                        fixed = case[symbol, frame, variant]
                        stress_rows.append({"symbol": symbol, "timeframe": frame,
                                            "variant": variant, "cost_bps_per_side": cost,
                                            "full_period_pnl_rub": fixed["full_period_pnl_rub"],
                                            "full_period_return_pct": fixed["full_period_return_pct"],
                                            "profitable_months": fixed["profitable_months"],
                                            "months": fixed["months"],
                                            "worst_month_pnl_rub": fixed["worst_month_pnl_rub"]})
                        continue
                    curve, trades = [], []
                    result = simulate(bars, signals, gate, gate, 0.0, PROTOCOL["start"],
                                      fee_bps=cost, equity_curve=curve, trade_log=trades,
                                      exit_signals=exits)
                    observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= PROTOCOL["start"]}
                    months = [item for item in continuous_monthly_windows(
                        bars, curve, trades, 2024, PROTOCOL["split"])["all"]
                              if item["start"][:7] in observed]
                    stress_rows.append({"symbol": symbol, "timeframe": frame,
                                        "variant": variant, "cost_bps_per_side": cost,
                                        "full_period_pnl_rub": result["pnl_rub"],
                                        "full_period_return_pct": result["return_pct"],
                                        "profitable_months": sum(item["pnl_rub"] > 0 for item in months),
                                        "months": len(months),
                                        "worst_month_pnl_rub": min(item["pnl_rub"] for item in months)})
            if count % 50 == 0:
                print(f"stress {frame}: {count}/{len(stress_symbols[frame])}", flush=True)
    write_csv(OUT / "cost_stress.csv", stress_rows)
    lines = ["# Проверка параметров Turtle по времени и расходам", "",
             "Два временных перехода на уже просмотренной истории: выбор одной пары для всего "
             "таймфрейма на ранних месяцах, затем проверка без перенастройки на более поздних. "
             "Это **не слепой holdout**. В каждый train включены только бумаги со всеми нужными "
             "полными месяцами; пропущенные в test показаны отдельно. "
             "[Все варианты](walk_forward.csv), [соседние значения](neighbor_stability.csv), "
             "[стресс расходов по каждому инструменту](cost_stress.csv).", "",
             "| Переход | TF | Выбрано на train | Бумаг train/test | Test: медиана прибыльных месяцев | Test: медианный PnL | 55/20: медиана прибыльных месяцев |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for fold in PLAN["folds"]:
        for frame in PROTOCOL["signal_timeframes"]:
            variant = selected[frame, fold["name"]]
            row = next(r for r in wf_rows if r["fold"] == fold["name"] and r["timeframe"] == frame
                       and r["variant"] == variant)
            ref = next(r for r in wf_rows if r["fold"] == fold["name"] and r["timeframe"] == frame
                       and r["variant"] == "dennis_turtle_55_20")
            lines.append(f"| {fold['name']} | {frame} | {variant.removeprefix('dennis_turtle_').replace('_','/')} | "
                         f"{row['train_symbols']}/{row['test_symbols']} | "
                         f"{row['test_median_positive_month_share_pct']:.1f}% | "
                         f"{row['test_median_period_pnl_rub']:,.0f} ₽ | "
                         f"{ref['test_median_positive_month_share_pct']:.1f}% |")
    lines += ["", "## Расходы", "",
              "5/15/25 б.п. на сторону — соответственно только комиссия / базовая модель "
              "комиссия + проскальзывание / ухудшенное исполнение. Значения считаются как "
              "денежный эквивалент расходов; цена исполнения не сдвигается. "
              "В таблице медиана результата по одинаковым полным историям инструментов.", "",
              "| TF | Пара | Расходы на сторону | Бумаг с плюсом | Медиана за период | Медиана прибыльных месяцев |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    grouped = defaultdict(list)
    for row in stress_rows:
        grouped[row["timeframe"], row["variant"], int(row["cost_bps_per_side"])].append(row)
    for key, group in sorted(grouped.items()):
        frame, variant, cost = key
        med_ret = statistics.median(float(r["full_period_return_pct"]) for r in group)
        med_months = statistics.median(int(r["profitable_months"]) for r in group)
        positive = sum(float(r["full_period_pnl_rub"]) > 0 for r in group)
        lines.append(f"| {frame} | {variant.removeprefix('dennis_turtle_').replace('_','/')} | "
                     f"{cost} б.п. | {positive}/{len(group)} | {med_ret:+.2f}% | {med_months:g}/33 |")
    lines += ["", "Соседние параметры и расходы — диагностика чувствительности, "
              "не основание менять уже работающие счета. Финальный слепой период "
              "начнётся только на новых данных после 2026-11-04. Дивиденды, корпоративные "
              "события и стоимость short всё ещё не учтены.", ""]
    (OUT / "WALK_FORWARD_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    print(OUT / "WALK_FORWARD_REVIEW.md", flush=True)


if __name__ == "__main__":
    main()
