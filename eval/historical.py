"""Numeric historical return check before registering virtual accounts."""

from __future__ import annotations

import math
import argparse
import json
import shutil
from pathlib import Path

from guardrails.policy import load_policy


def trailing_year_gate(stocks: list[dict]) -> tuple[bool, list[str]]:
    """Require every selected stock to exceed the policy's net trailing 12-month return.

    `recent_periods["12"]` is a complete rolling 12-month window. Calendar YTD
    and full-history returns must never substitute for it.
    """
    threshold = load_policy()["experiment"]["min_trailing_12m_return_pct_after_costs"]
    failures = []
    for stock in stocks:
        symbol = str(stock.get("symbol") or "unknown")
        period = stock.get("recent_periods", {}).get("12") or {}
        value = period.get("return_pct")
        months = (period.get("from_month"), period.get("through_month"))
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value) or not all(months)):
            failures.append(f"{symbol}: нет полного 12-месячного результата после расходов")
        elif value <= threshold:
            failures.append(f"{symbol}: {value:+g}% за последние 12 месяцев (требуется >{threshold:g}%)")
    return not failures, failures


def selected_history_gate(selection: dict, history: dict) -> tuple[bool, list[str]]:
    """Audit a registered strategy against the same threshold, using its saved history."""
    selected = selection.get("top10", [])
    failures = []
    if not selected:
        failures.append("нет выбранных акций")
    stocks = []
    for row in selected:
        symbol = row.get("symbol")
        period = history.get("symbols", {}).get(symbol, {}).get("after", {}).get("periods", {}).get("12")
        stocks.append({"symbol": symbol, "recent_periods": {"12": period} if period else {}})
    passed, returns = trailing_year_gate(stocks)
    return passed and not failures, failures + returns


def rolling_windows(months: list[dict], length: int) -> list[dict]:
    """Every contiguous complete window, compounded from monthly returns."""
    ordered = sorted(months, key=lambda row: row["month"])
    windows = []
    for index in range(len(ordered) - length + 1):
        group = ordered[index:index + length]
        sequence = [int(row["month"][:4]) * 12 + int(row["month"][5:7]) for row in group]
        values = [row.get("return_pct") for row in group]
        if (sequence != list(range(sequence[0], sequence[0] + length))
                or any(not isinstance(value, (int, float)) or not math.isfinite(value)
                       for value in values)):
            continue
        growth = math.prod(1 + value / 100 for value in values)
        windows.append({"from_month": group[0]["month"], "through_month": group[2]["month"],
                        "return_pct": round((growth - 1) * 100, 4)})
    return windows


def rolling_three_months(months: list[dict]) -> list[dict]:
    return rolling_windows(months, 3)


def report_strategy(selection: dict, history: dict) -> dict:
    policy = load_policy()["experiment"]
    threshold = policy["min_trailing_12m_return_pct_after_costs"]
    rows = []
    for selected in selection.get("top10", []):
        symbol = selected["symbol"]
        saved = history.get("symbols", {}).get(symbol, {}).get("after", {})
        period = saved.get("periods", {}).get("12") or {}
        value = period.get("return_pct")
        complete = (isinstance(value, (int, float)) and not isinstance(value, bool)
                    and math.isfinite(value) and period.get("from_month") and period.get("through_month"))
        windows = rolling_three_months(saved.get("months", []))
        annual_windows = rolling_windows(saved.get("months", []), 12)
        passed = bool(complete and value > threshold)
        rows.append({"symbol": symbol, "status": "PASS_12M" if passed else "FAIL_12M",
                     "trailing_12m": period or None,
                     "rolling_3m_windows": windows,
                     "rolling_3m_positive_windows": sum(row["return_pct"] > 0 for row in windows),
                     "rolling_3m_window_count": len(windows),
                     "rolling_12m_windows": annual_windows,
                     "reason": None if passed else (f"{value:+g}% <= {threshold:g}%" if complete
                                                   else "нет полного 12-месячного результата после расходов")})
    passed_count = sum(row["status"] == "PASS_12M" for row in rows)
    return {"strategy_id": selection.get("id"), "cost_mode": "after",
            "criteria": {"trailing_12m_return_pct": f">{threshold:g}",
                         "rolling_3m": policy["rolling_3m_decision"],
                         "rolling_3m_scope": policy["rolling_3m_windows"],
                         "rolling_12m": policy["rolling_12m_decision"],
                         "rolling_12m_scope": policy["rolling_12m_windows"],
                         "min_paper_stocks": policy["min_paper_stocks"]},
            "selected_count": len(rows), "passed_count": passed_count,
            "strategy_status": "PAPER_CANDIDATE" if passed_count >= policy["min_paper_stocks"]
                               else "NO_PASSING_STOCKS",
            "stocks": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategies-root", type=Path, default=Path(__file__).resolve().parents[1] / "strategies")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "results/paper_selection.json")
    parser.add_argument("--prune-live", action="store_true", help="remove failed configured accounts and their virtual journals")
    parser.add_argument("--setups", type=Path, default=Path(__file__).resolve().parents[1] / "papertrading/setups/fleet")
    parser.add_argument("--live", type=Path, default=Path(__file__).resolve().parents[1] / "papertrading/live")
    args = parser.parse_args()
    strategies = []
    for path in sorted(args.strategies_root.glob("*/selection.json")):
        history_path = path.with_name("history_snapshot.json")
        if not history_path.is_file():
            continue
        strategies.append(report_strategy(json.loads(path.read_text()), json.loads(history_path.read_text())))
    report = {"policy": "guardrails/POLICY.json", "strategies": strategies}
    threshold = load_policy()["experiment"]["min_trailing_12m_return_pct_after_costs"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Отбор акций для paper trading", "",
             f"Первый допуск: **строго >{threshold:g}%** после расходов за последние полные 12 месяцев "
             "по каждой акции. Все непрерывные трёхмесячные и годовые окна сохранены в "
             "[машинном отчёте](paper_selection.json) для оценки устойчивости; "
             "для них нет дополнительного порога допуска.", "",
             f"Хотя бы одна акция прошла порог у "
             f"{sum(strategy['strategy_status'] == 'PAPER_CANDIDATE' for strategy in strategies)} "
             f"из {len(strategies)} стратегий. Допуск оценивается по каждой акции; "
             "фиксированного размера корзины нет.", "",
             "| Стратегия | Акция | 12 месяцев | 3 месяца | Положительных 3-месячных окон | Худшее 3-месячное окно | Допуск |",
             "| --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for strategy in strategies:
        for stock in strategy["stocks"]:
            last_year = stock["trailing_12m"] or {}
            last_three = stock["rolling_3m_windows"][-1] if stock["rolling_3m_windows"] else {}
            worst = min((row["return_pct"] for row in stock["rolling_3m_windows"]), default=None)
            fmt = lambda value: "—" if value is None else f"{value:+.2f}%"
            lines.append(f"| `{strategy['strategy_id']}` | {stock['symbol']} | "
                         f"{fmt(last_year.get('return_pct'))} | {fmt(last_three.get('return_pct'))} | "
                         f"{stock['rolling_3m_positive_windows']}/{stock['rolling_3m_window_count']} | "
                         f"{fmt(worst)} | {stock['status']} |")
    args.output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    removed = []
    if args.prune_live:
        allowed = {(strategy["strategy_id"], stock["symbol"])
                   for strategy in strategies for stock in strategy["stocks"]
                   if stock["status"] == "PASS_12M"}
        screened = {strategy["strategy_id"] for strategy in strategies}
        for setup_path in sorted(args.setups.glob("*.json")):
            setup = json.loads(setup_path.read_text())
            strategy_id, symbol = setup["strategy"], setup["symbol"]
            if strategy_id not in screened or (strategy_id, symbol) in allowed:
                continue
            account_id = setup["account_id"]
            if not account_id or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in account_id):
                raise ValueError(f"unsafe account ID: {account_id!r}")
            account_dir = args.live / account_id
            setup_path.unlink()
            if account_dir.is_dir():
                shutil.rmtree(account_dir)
            removed.append(account_id)
        fleet_path = args.live / "fleet_status.json"
        if fleet_path.is_file():
            fleet = json.loads(fleet_path.read_text())
            fleet["accounts"] = [row for row in fleet.get("accounts", [])
                                 if row.get("account_id") not in removed]
            fleet_path.write_text(json.dumps(fleet, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"strategies": len(strategies),
                      "stocks": sum(row["selected_count"] for row in strategies),
                      "passed": sum(row["passed_count"] for row in strategies),
                      "removed_accounts": removed}, ensure_ascii=False))


if __name__ == "__main__":
    main()
