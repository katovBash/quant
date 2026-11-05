"""Evaluate a frozen strategy on genuinely new, paired equity observations."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
from datetime import date
from pathlib import Path

try:
    from guardrails.policy import load_policy
except ModuleNotFoundError:  # direct `python3 eval/evaluate.py` invocation
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from guardrails.policy import load_policy

FORWARD_POLICY = load_policy()["forward_evidence"]


def read_equity(path: Path, frozen: date) -> tuple[list[date], list[float], list[float]]:
    dates, strategy, baseline = [], [], []
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"date", "strategy_equity", "baseline_equity"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"equity CSV needs {sorted(required)}")
        for row in reader:
            day = date.fromisoformat(row["date"])
            if day <= frozen or (dates and day <= dates[-1]):
                raise ValueError("equity dates must be strictly increasing and after frozen date")
            a, b = float(row["strategy_equity"]), float(row["baseline_equity"])
            if not all(math.isfinite(x) and x > 0 for x in (a, b)):
                raise ValueError("equity must be positive and finite")
            dates.append(day)
            strategy.append(a)
            baseline.append(b)
    if len(dates) < 2:
        raise ValueError("at least two equity observations are required")
    return dates, strategy, baseline


def count_trades(path: Path, frozen: date) -> int:
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if "exit_date" not in (reader.fieldnames or []):
            raise ValueError("closed-trades CSV needs exit_date")
        count = 0
        for row in reader:
            if date.fromisoformat(row["exit_date"]) <= frozen:
                raise ValueError("closed trade predates frozen strategy")
            count += 1
    return count


def max_drawdown_pct(equity: list[float]) -> float:
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        worst = min(worst, 100 * (value / peak - 1))
    return worst


def block_bootstrap_p(differences: list[float], block: int, draws: int, seed: int) -> float:
    """One-sided test of mean paired daily excess return <= 0, with circular blocks."""
    n = len(differences)
    observed = statistics.mean(differences)
    centered = [x - observed for x in differences]
    rng = random.Random(seed)
    exceed = 0
    for _ in range(draws):
        sample = []
        while len(sample) < n:
            start = rng.randrange(n)
            sample.extend(centered[(start + j) % n] for j in range(block))
        if statistics.mean(sample[:n]) >= observed:
            exceed += 1
    return (exceed + 1) / (draws + 1)


def classify_paper(
    dates: list[date], strategy: list[float], *, started: date,
    initial_capital: float, costs_verified: bool, has_short: bool,
    short_costs_verified: bool,
) -> dict:
    """Operational 30-day paper category; never a real-money or edge approval."""
    if not math.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("paper initial capital must be positive and finite")
    if len(dates) != len(strategy):
        raise ValueError("paper dates and equity have different lengths")
    if not dates:
        return {"paper_status": "NO_DATA", "paper_calendar_days": 0,
                "paper_return_pct": None}
    calendar_days = (dates[-1] - started).days
    if calendar_days < 0:
        raise ValueError("paper start must not follow the latest equity date")
    paper_return_pct = 100 * (strategy[-1] / initial_capital - 1)
    if len(dates) < 2 or calendar_days < load_policy()["paper"]["first_review_after_calendar_days"]:
        paper_status = "OBSERVING"
    elif not costs_verified or (has_short and not short_costs_verified):
        paper_status = "COSTS_UNVERIFIED"
    elif paper_return_pct > load_policy()["paper"]["continue_requires_net_return_above_pct"]:
        paper_status = "APPROVED_30D_PAPER"
    else:
        paper_status = "NOT_APPROVED_30D"
    return {"paper_status": paper_status, "paper_calendar_days": calendar_days,
            "paper_return_pct": round(paper_return_pct, 4)}


def evaluate(
    dates: list[date], strategy: list[float], baseline: list[float],
    closed_trades: int, *, min_trades: int = FORWARD_POLICY["min_new_closed_trades"],
    min_days: int = FORWARD_POLICY["min_distinct_trading_dates"],
    tested_variants: int = 1,
    max_drawdown_limit: float = FORWARD_POLICY["max_drawdown_pct"],
    costs_verified: bool = False, short_costs_verified: bool = False,
    has_short: bool = False, draws: int = 2000, block: int = 10, seed: int = 42,
    paper_started: date | None = None, paper_initial_capital: float | None = None,
) -> dict:
    if not (len(dates) == len(strategy) == len(baseline)) or len(dates) < 2:
        raise ValueError("paired equity series must have equal length >= 2")
    if min_trades < 1 or min_days < 2 or tested_variants < 1 or draws < 100 or block < 1:
        raise ValueError("invalid evaluation settings")
    daily_excess = [
        strategy[i] / strategy[i - 1] - baseline[i] / baseline[i - 1]
        for i in range(1, len(dates))
    ]
    p = block_bootstrap_p(daily_excess, min(block, len(daily_excess)), draws, seed)
    adjusted_p = min(1.0, p * tested_variants)
    excess_pct = 100 * (strategy[-1] / strategy[0] - baseline[-1] / baseline[0])
    dd = max_drawdown_pct(strategy)
    paper = classify_paper(
        dates, strategy, started=paper_started or dates[0],
        initial_capital=strategy[0] if paper_initial_capital is None else paper_initial_capital,
        costs_verified=costs_verified, has_short=has_short,
        short_costs_verified=short_costs_verified,
    )
    reasons = []
    if closed_trades < min_trades:
        reasons.append(f"fewer than {min_trades} new closed trades")
    if len(dates) < min_days:
        reasons.append(f"fewer than {min_days} distinct trading dates")
    if not costs_verified:
        reasons.append("execution costs not verified")
    if has_short and not short_costs_verified:
        reasons.append("short borrow and dividend costs not verified")
    if reasons:
        status = "INSUFFICIENT_EVIDENCE"
    elif (excess_pct <= 0 or dd < -max_drawdown_limit
          or adjusted_p >= FORWARD_POLICY["adjusted_one_sided_p_below"]):
        status = "NO_RELIABLE_EDGE_DETECTED"
    else:
        status = "FORWARD_EVIDENCE_OF_EDGE"
    return {
        "status": status,
        **paper,
        "paper_note": "30-day approval means positive observed paper equity after verified costs; it is not evidence of a reliable future edge or approval for real trading",
        "reasons": reasons,
        "new_closed_trades": closed_trades,
        "trading_dates": len(dates),
        "net_excess_return_pp": round(excess_pct, 4),
        "max_drawdown_pct": round(dd, 4),
        "one_sided_block_bootstrap_p": round(p, 6),
        "bonferroni_adjusted_p": round(adjusted_p, 6),
        "tested_variants": tested_variants,
        "bootstrap_draws": draws,
        "block_length": min(block, len(daily_excess)),
        "note": "p is not the probability that the strategy is random; evidence is conditional on honest, frozen, net-of-cost inputs",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--equity", type=Path, required=True)
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--frozen-on", type=date.fromisoformat, required=True)
    parser.add_argument("--paper-started", type=date.fromisoformat,
                        help="paper account start date; defaults to first equity observation")
    parser.add_argument("--paper-initial-capital", type=float,
                        help="initial virtual capital; defaults to first equity observation")
    parser.add_argument("--tested-variants", type=int, default=1)
    parser.add_argument("--min-trades", type=int, default=FORWARD_POLICY["min_new_closed_trades"])
    parser.add_argument("--min-days", type=int, default=FORWARD_POLICY["min_distinct_trading_dates"])
    parser.add_argument("--max-drawdown-pct", type=float, default=FORWARD_POLICY["max_drawdown_pct"])
    parser.add_argument("--costs-verified", action="store_true")
    parser.add_argument("--has-short", action="store_true")
    parser.add_argument("--short-costs-verified", action="store_true")
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--block", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    dates, strategy, baseline = read_equity(args.equity, args.frozen_on)
    result = evaluate(
        dates, strategy, baseline, count_trades(args.trades, args.frozen_on),
        min_trades=args.min_trades, min_days=args.min_days,
        tested_variants=args.tested_variants, max_drawdown_limit=args.max_drawdown_pct,
        costs_verified=args.costs_verified, has_short=args.has_short,
        short_costs_verified=args.short_costs_verified, draws=args.draws,
        block=args.block, seed=args.seed, paper_started=args.paper_started,
        paper_initial_capital=args.paper_initial_capital,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
