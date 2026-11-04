"""Promote one historically screened experiment row into a frozen candidate.

This is a structural and historical gate, not proof of future profitability.
The review fields are human attestations, not facts verified by this program.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import shutil
from pathlib import Path

from criteria.screen_historical import screen

ROOT = Path(__file__).resolve().parents[1]
REVIEW_FLAGS = ("no_lookahead_checked", "stable_neighbors_checked",
                "control_checked", "costs_checked", "cross_ticker_checked")


def contained(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError as exc:
        raise ValueError(f"file must remain inside experiment: {relative}") from exc
    if not path.is_file():
        raise ValueError(f"missing experiment file: {relative}")
    return path


def chosen_row(source: Path, selector: dict) -> dict:
    opener = gzip.open if source.suffix == ".gz" else open
    with opener(source, "rt", encoding="utf-8-sig", newline="") as stream:
        found = [row for row in csv.DictReader(stream)
                 if all(str(row.get(key, "")) == str(value) for key, value in selector.items())]
    if len(found) != 1:
        raise ValueError(f"selector must match exactly one result row; found {len(found)}")
    return found[0]


def prepare(experiment: Path, root: Path = ROOT) -> tuple[dict, Path, Path, Path, Path, dict, Path]:
    experiment = experiment.resolve()
    try:
        experiment.relative_to((root / "experiments").resolve())
    except ValueError as exc:
        raise ValueError("candidate must come from experiments/") from exc
    spec = json.loads((experiment / "candidate.json").read_text(encoding="utf-8"))
    slug = spec["slug"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("slug must use lowercase letters, digits and hyphens")
    selector = spec["selector"]
    if not selector or not {"symbol", "timeframe"} <= set(selector):
        raise ValueError("selector needs symbol and timeframe")
    scope = spec.get("scope")
    symbols = spec.get("symbols", [])
    if scope not in ("single_ticker", "basket", "universal"):
        raise ValueError("scope must be single_ticker, basket or universal")
    if scope == "single_ticker" and symbols != [selector["symbol"]]:
        raise ValueError("single_ticker scope needs only the selected symbol")
    if scope == "basket" and (len(set(symbols)) < 2 or selector["symbol"] not in symbols):
        raise ValueError("basket scope needs selected symbol and another ticker")
    if scope == "universal" and not spec.get("universe"):
        raise ValueError("universal scope needs an explicit universe")
    review = spec["review"]
    stage = spec.get("review_stage", "historical_candidate")
    if stage not in ("historical_candidate", "tv_review"):
        raise ValueError("unknown review_stage")
    required_flags = (flag for flag in REVIEW_FLAGS
                      if not (stage == "tv_review" and flag == "costs_checked")
                      and not (scope == "single_ticker" and flag == "cross_ticker_checked"))
    if any(review.get(flag) is not True for flag in required_flags):
        raise ValueError("all review flags must be true and documented")
    if not review.get("notes") or not spec.get("rule") or not spec.get("frozen_on"):
        raise ValueError("rule, frozen_on and review notes are required")
    source = contained(experiment, spec["source_csv"])
    pine = contained(experiment, spec["pine"])
    if not spec.get("python"):
        raise ValueError("candidate requires both pine and python strategy files")
    python = contained(experiment, spec["python"])
    row = chosen_row(source, selector)
    failures = screen(row)
    if failures:
        raise ValueError("historical screen failed: " + ", ".join(failures))
    monthly = contained(experiment, spec["monthly_report"])
    monthly_data = json.loads(monthly.read_text(encoding="utf-8"))
    selected_variant = row.get("variant", selector.get("variant"))
    matching = [pair for pair in monthly_data.get("pairs", [])
                if pair.get("symbol") == selector["symbol"]
                and pair.get("timeframe") == selector["timeframe"]
                and (selected_variant is None or pair.get("variant") == selected_variant)]
    if len(matching) != 1:
        raise ValueError("monthly report needs exactly one selected pair")
    months = (matching[0].get("continuous_months") or
              (matching[0].get("monthly_start_windows") or {}).get("1", {}))
    individual = months.get("all", [])
    if (len(individual) < 2 or len(individual) != months.get("count")
            or len({item.get("start") for item in individual}) != len(individual)
            or any(not item.get("start") or any(field not in item for field in
                   ("pnl_rub", "return_pct", "closed_trades", "winning_trades"))
                   or not 0 <= int(item["winning_trades"]) <= int(item["closed_trades"])
                   for item in individual)):
        raise ValueError("monthly report needs distinct months with PnL and deal counts")
    pnls = [float(item["pnl_rub"]) for item in individual]
    robustness = {"monthly_report": spec["monthly_report"],
                  "months": len(individual),
                  "profitable_months": sum(pnl > 0 for pnl in pnls),
                  "profitable_month_share_pct": round(100 * sum(pnl > 0 for pnl in pnls) / len(pnls), 2),
                  "worst_month_pnl_rub": min(pnls),
                  "trade_window_report": spec.get("trade_window_report")}
    if spec.get("trade_window_report"):
        contained(experiment, spec["trade_window_report"])
    destination = root / "strategies" / slug
    if destination.exists():
        raise ValueError(f"strategy already exists: {slug}")
    return spec, source, pine, python, monthly, robustness, destination


def promote(experiment: Path, root: Path = ROOT, *, apply: bool = False) -> dict:
    spec, source, pine, python, monthly, robustness, destination = prepare(experiment, root)
    stage = spec.get("review_stage", "historical_candidate")
    scope = spec["scope"]
    symbols = spec.get("symbols", [])
    status = "TV_REVIEW" if stage == "tv_review" else "HISTORICAL_CANDIDATE"
    report = {"status": status, "destination": str(destination),
              "experiment": str(experiment.resolve()), "applied": apply}
    if not apply:
        return report
    destination.mkdir(parents=True)
    shutil.copy2(pine, destination / "strategy.pine")
    shutil.copy2(python, destination / "strategy.py")
    (destination / "robustness.json").write_text(
        json.dumps(robustness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    relative_experiment = Path("../..") / experiment.resolve().relative_to(root.resolve())
    selector = ", ".join(f"{key}={value}" for key, value in spec["selector"].items())
    (destination / "README.md").write_text(
        f"# {spec['slug']} · {status}\n\n"
        f"{spec['rule']}\n\n"
        f"Область применения: `{scope}`. "
        f"Тикеры: {', '.join(symbols) if symbols else spec.get('universe', '')}.\n\n"
        f"Зафиксировано: {spec['frozen_on']}. Исходный [эксперимент]({relative_experiment}/README.md), "
        f"строка `{selector}` в `{spec['source_csv']}`. "
        "Полный перебор, топы и неудачные варианты остаются в эксперименте.\n\n"
        "[Pine для TradingView](strategy.pine) и [Python-сигнал](strategy.py). " +
        "Перенос не запускает paper trading. Исторический проход не доказывает будущую прибыль.\n\n" +
        ("Ожидает ручной сверки в TradingView и проверки оставшихся расходов перед paper trading.\n\n"
           if stage == "tv_review" else "") +
        f"Ручной обзор: {spec['review']['notes']}\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--apply", action="store_true", help="copy frozen code after dry run")
    args = parser.parse_args()
    print(json.dumps(promote(args.experiment, apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
