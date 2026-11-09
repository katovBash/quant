"""Publish reproducible experiment and virtual-account lifecycle decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    from guardrails.policy import load_policy
    from eval.historical import trailing_year_gate
except ModuleNotFoundError:  # direct `python3 guardrails/lifecycle.py` invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from guardrails.policy import load_policy
    from eval.historical import trailing_year_gate

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def experiment_gate(review: dict | None) -> tuple[str, list[str]]:
    if review is None:
        return "NO_EXPERIMENT_REVIEW", ["Нет машинного отчёта PAPER_REVIEW"]
    decision = review.get("decision") or {}
    if decision.get("status") == "CLOSED":
        return "EXPERIMENT_CLOSED", [str(decision.get("reason") or "Исследование закрыто")]
    validation = review.get("validation", {})
    if not validation.get("structural_ok"):
        return "EXPERIMENT_INVALID", ["Структурная проверка эксперимента не пройдена"]
    policy = load_policy()["experiment"]
    if not review.get("rule") or len(review.get("stocks", [])) < policy["min_paper_stocks"]:
        return "EXPERIMENT_REVIEW", ["Не выбраны одно правило и прошедшие акции"]
    if review.get("review_version", 1) >= 2:
        ranked = review.get("candidate_rules") or []
        screened = review.get("rule_screening") or []
        summary = review.get("screening_summary") or {}
        rule = review["rule"]
        if review.get("selection_method") == "first_train_rank_with_passing_stocks":
            chosen = next((item for item in screened
                           if item.get("passed_trailing_12m", 0) >= policy["min_paper_stocks"]), None)
            count_key = "selected_passed"
        else:
            chosen = screened[0] if screened else None
            count_key = "best_by_train_passed"
        if (not ranked or len(screened) != len(ranked)
                or chosen is None
                or (chosen.get("timeframe"), chosen.get("variant"))
                   != (rule.get("timeframe"), rule.get("variant"))
                or summary.get("rules_checked") != len(screened)
                or summary.get(count_key) != chosen.get("passed_trailing_12m")
                or chosen.get("passed_trailing_12m", 0) < len(review["stocks"])
                or (review.get("selection_scope") == "all_passing"
                    and chosen.get("passed_trailing_12m") != len(review["stocks"]))):
            return "EXPERIMENT_REVIEW", ["Не подтверждена проверка всех настроек по годовому порогу"]
    cost_status = str(review.get("protocol", {}).get("cost_status") or "")
    if not cost_status.startswith("after_"):
        return "EXPERIMENT_REVIEW", ["История посчитана до расходов"]
    if any(stock.get("candle_quality", {}).get("status") != "basic_check_ok"
           for stock in review["stocks"]):
        return "EXPERIMENT_REVIEW", ["Качество свечей выбранных акций не подтверждено"]
    passed, failures = trailing_year_gate(review["stocks"])
    if not passed:
        return "RETURN_BELOW_PAPER_THRESHOLD", failures
    warnings = []
    if validation.get("corporate_actions", {}).get("status") != "complete":
        warnings.append("Покрытие дивидендов или сплитов неполное; выход к реальным сделкам закрыт")
    if validation.get("monthly_validation", {}).get("gap_pairs", 0):
        warnings.append("В исходной вселенной есть календарные пропуски")
    return "PAPER_CANDIDATE", warnings


def account_gate(paper_status: str | None) -> str:
    return {
        None: "WAITING_FOR_FIRST_POLL",
        "NO_DATA": "WAITING_FOR_FIRST_POLL",
        "OBSERVING": "PAPER_OBSERVING",
        "APPROVED_30D_PAPER": "PAPER_CONTINUE",
        "NOT_APPROVED_30D": load_policy()["paper"]["negative_30d_result"],
        "COSTS_UNVERIFIED": "COST_REVIEW",
    }.get(paper_status, "PAPER_ERROR_REVIEW")


def build(live_root: Path, setup_root: Path, strategies_root: Path) -> dict:
    setups = defaultdict(list)
    for path in sorted(setup_root.glob("*.json")):
        setup = read_json(path)
        setups[setup["strategy"]].append({"account_id": setup["account_id"],
                                          "symbol": setup["symbol"]})
    entries = []
    for strategy_id, configured in sorted(setups.items()):
        selection_path = strategies_root / strategy_id / "selection.json"
        selection = read_json(selection_path) if selection_path.exists() else {}
        source = selection.get("source_review")
        review_path = ROOT / source if source else None
        review = read_json(review_path) if review_path and review_path.exists() else None
        historical_gate, warnings = experiment_gate(review)
        accounts = []
        for item in configured:
            status_path = live_root / item["account_id"] / "paper_status.json"
            paper = read_json(status_path) if status_path.exists() else {}
            accounts.append({**item, "stage": account_gate(paper.get("paper_status")),
                             "paper_status": paper.get("paper_status"),
                             "days": paper.get("paper_calendar_days"),
                             "return_pct": paper.get("paper_return_pct")})
        counts = dict(Counter(account["stage"] for account in accounts))
        if historical_gate not in ("PAPER_CANDIDATE",):
            stage = "PAPER_GATE_FAILED"
        elif not accounts or all(account["stage"] == "WAITING_FOR_FIRST_POLL" for account in accounts):
            stage = "PAPER_QUEUED"
        elif any(account["stage"] == "PAPER_STOP_REVIEW" for account in accounts):
            stage = "PAPER_STOP_REVIEW"
        elif any(account["stage"] == "PAPER_ERROR_REVIEW" for account in accounts):
            stage = "PAPER_ERROR_REVIEW"
        elif all(account["stage"] == "PAPER_CONTINUE" for account in accounts):
            stage = "PAPER_CONTINUE"
        elif any(account["stage"] == "COST_REVIEW" for account in accounts):
            stage = "COST_REVIEW"
        else:
            stage = "PAPER_OBSERVING"
        forward_path = strategies_root / strategy_id / "forward_evidence.json"
        forward = read_json(forward_path) if forward_path.exists() else {}
        if (stage == "PAPER_CONTINUE" and review
                and review.get("validation", {}).get("corporate_actions", {}).get("status") == "complete"):
            stage = "EXIT_REVIEW"
        entries.append({"strategy_id": strategy_id, "stage": stage,
                        "experiment_gate": historical_gate, "warnings": warnings,
                        "configured_accounts": len(accounts), "account_stages": counts,
                        "accounts": accounts, "forward_evidence_status": forward.get("status"),
                        "real_trading_enabled": False})
    return {"model": "guardrails/POLICY.json", "strategies": entries,
            "real_trading_enabled": False}


def publish(live_root: Path, setup_root: Path, strategies_root: Path) -> dict:
    result = build(live_root, setup_root, strategies_root)
    live_root.mkdir(parents=True, exist_ok=True)
    (live_root / "LIFECYCLE.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Этапы стратегий", "",
             "Автоматическая оценка виртуальных счетов. `EXIT_REVIEW` означает разбор перед "
             "решением о реальных сделках; реальные заявки эта система не включает.", "",
             "| Стратегия | Этап | Счетов | Эксперимент |",
             "| --- | --- | ---: | --- |"]
    for row in result["strategies"]:
        lines.append(f"| `{row['strategy_id']}` | `{row['stage']}` | "
                     f"{row['configured_accounts']} | `{row['experiment_gate']}` |")
    lines += ["", "[Точная модель переходов](../../guardrails/POLICY.json) · "
              "[машинные статусы](LIFECYCLE.json)", ""]
    (live_root / "LIFECYCLE.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-root", type=Path, default=ROOT / "papertrading/live")
    parser.add_argument("--setup-root", type=Path, default=ROOT / "papertrading/setups/fleet")
    parser.add_argument("--strategies-root", type=Path, default=ROOT / "strategies")
    args = parser.parse_args()
    result = publish(args.live_root, args.setup_root, args.strategies_root)
    print(json.dumps({"strategies": len(result["strategies"]),
                      "stages": dict(Counter(row["stage"] for row in result["strategies"]))},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
