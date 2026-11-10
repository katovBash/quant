"""Register a validated fixed rule and one virtual account per passing stock."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from papertrading.setup import load_setup
from guardrails.lifecycle import experiment_gate
from scripts.build_strategy_history import build_strategy
from prepare import report_text


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def activate(review_path: Path, strategy_dir: Path) -> dict:
    review_path = review_path.resolve()
    strategy_dir = strategy_dir.resolve()
    if strategy_dir.parent != ROOT / "strategies":
        raise ValueError("strategy folder must be directly inside strategies/")
    review = read_json(review_path)
    if review.get("review_version", 1) < 2 and not review.get("activation"):
        raise ValueError("rerun paper review to screen every fixed rule before new activation")
    gate, warnings = experiment_gate(review)
    if gate != "PAPER_CANDIDATE":
        raise ValueError("paper activation gate failed: " + gate + "; " + "; ".join(warnings))
    rule = review.get("rule")
    stocks = review.get("stocks", [])
    if (not review.get("validation", {}).get("structural_ok") or not rule
            or len(stocks) < 1):
        raise ValueError("validated fixed rule and at least one passing stock required")
    if review["protocol"].get("cost_status") == "gross_before_costs":
        raise ValueError("paper activation requires an after-cost historical run")
    if any(item.get("candle_quality", {}).get("status") != "basic_check_ok" for item in stocks):
        raise ValueError("selected stock has uncertain or invalid candles")
    strategy_path = strategy_dir / "strategy.py"
    for name in ("strategy.py", "strategy.pine", "parity.json"):
        if not (strategy_dir / name).exists():
            raise ValueError(f"missing strategy artifact: {name}")
    spec = importlib.util.spec_from_file_location("paper_review_candidate", strategy_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot import fixed strategy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    symbols = [item["symbol"] for item in stocks]
    if (getattr(module, "STRATEGY_ID", None) != strategy_dir.name
            or getattr(module, "TIMEFRAME", None) != rule["timeframe"]
            or list(getattr(module, "PAPER_SYMBOLS", [])) != symbols
            or not callable(getattr(module, "signal", None))):
        raise ValueError("Python strategy scope differs from frozen recommendation")
    parity = read_json(strategy_dir / "parity.json")
    if (parity.get("strategy_id") != strategy_dir.name
            or parity.get("variant") != rule["variant"]
            or parity.get("timeframe") != rule["timeframe"]
            or parity.get("bars_checked", 0) < 100
            or parity.get("mismatches") != 0):
        raise ValueError("Python signal parity with the historical rule is not verified")
    universe = read_json(ROOT / "data/candles/moex_scan/universe_2026-10-30.json")
    lots = {item["SECID"]: item["LOTSIZE"] for item in universe
            if isinstance(item.get("LOTSIZE"), int) and item["LOTSIZE"] > 0}
    if any(symbol not in lots for symbol in symbols):
        raise ValueError("lot size missing for a selected stock")
    mode = getattr(module, "PAPER_MODE", "long_short")
    cost = review["protocol"]
    fee = cost.get("commission_bps_per_side", 5)
    slip = cost.get("slippage_equivalent_bps_per_side", 10)
    setups = {}
    for symbol in symbols:
        target = ROOT / "papertrading/setups/fleet" / f"auto-{symbol.lower()}-{strategy_dir.name}.json"
        setup = {"account_id": f"{symbol}-{strategy_dir.name}".upper(),
                 "symbol": symbol, "strategy": strategy_dir.name,
                 "timeframe": rule["timeframe"], "initial_capital_rub": 1_000_000,
                 "position_weight_pct": 10, "mode": mode,
                 "lot_size_shares": lots[symbol], "fee_bps": fee, "slip_bps": slip,
                 "borrow_bps_annual": 0, "stop_loss_pct": None}
        if target.exists() and read_json(target) != setup:
            raise ValueError(f"existing setup differs; account history must not be overwritten: {target}")
        setups[target] = setup
    selection_path = strategy_dir / "selection.json"
    source_dir = review_path.parent
    source_rel = source_dir.relative_to(ROOT)
    selection = {"id": strategy_dir.name, "timeframe": rule["timeframe"],
                 "snapshot": review["protocol"].get("source_snapshot", ""),
                 "status": "HISTORICAL_RANKING", "cost_status": cost["cost_status"],
                 "source_review": str(review_path.relative_to(ROOT)),
                 "variant": rule["variant"],
                 "selection_rule": "one global variant ranked on train months; all passing liquid stocks ranked on train months",
                 "history_sources": {"after": {
                     "all_variants_csv": str(source_rel / "all_variants.csv"),
                     "monthly_csv": str(source_rel / "monthly_returns.csv"),
                     "variant": rule["variant"], "timeframe": rule["timeframe"]}},
                 "top10": [{"symbol": item["symbol"],
                            "net_return_pct": item["full_return_pct"],
                            "closed_trades": item["closed_trades"],
                            "train_positive_share_pct": item["train_positive_share_pct"],
                            "late_positive_share_pct": item["late_positive_share_pct"]}
                           for item in stocks]}
    if selection_path.exists() and read_json(selection_path) != selection:
        raise ValueError("existing selection differs; create a new strategy ID for changed rules")
    catalog_path = ROOT / "strategies/catalog.json"
    catalog = read_json(catalog_path)
    if any(item["id"] == strategy_dir.name and item["timeframe"] != rule["timeframe"]
           for item in catalog["rules"]):
        raise ValueError("catalog ID already has a different timeframe")
    if not any(item["id"] == strategy_dir.name for item in catalog["rules"]):
        catalog["rules"].append({"id": strategy_dir.name,
                                 "label": f"Turtle {rule['variant'][len('dennis_turtle_'):].replace('_', '/')} · {rule['timeframe']}"
                                 if rule["variant"].startswith("dennis_turtle_") else strategy_dir.name,
                                 "experiment": review_path.parent.parent.name,
                                 "timeframe": rule["timeframe"]})
    # All sources and collisions are checked before writing live configuration.
    write_json(selection_path, selection)
    write_json(catalog_path, catalog)
    snapshot = build_strategy(strategy_dir)
    write_json(strategy_dir / "history_snapshot.json", snapshot)
    for target, setup in setups.items():
        if not target.exists():
            write_json(target, setup)
        load_setup(target, strategy_dir.name)
    activation = {"status": "REGISTERED_AWAITING_POLL", "strategy_id": strategy_dir.name,
                  "accounts": [setup["account_id"] for setup in setups.values()],
                  "setup_files": [str(path.relative_to(ROOT)) for path in setups],
                  "paper_capital_rub_per_account": 1_000_000,
                  "paper_position_weight_pct": 10,
                  "note": "Fleet discovers frozen setups on its next poll; no real orders are sent."}
    review["activation"] = activation
    review["blockers"] = [item for item in review.get("blockers", [])
                          if not item.startswith("Python/Pine реализация")
                          and not item.startswith("фактические лоты")]
    review["blockers"].append("стоимость займа short и дивиденды выбранных бумаг не подтверждены")
    write_json(review_path, review)
    report = review_path.parent / "PAPER_REVIEW.md"
    protocol_path = review_path.parent.parent / "protocol.json"
    report.write_text(report_text(protocol_path, report.parent, review) +
                      "\n## Файлы виртуальной стратегии\n\n"
                      f"[Python, Pine и сверка сигналов]({os.path.relpath(strategy_dir, report.parent)}). "
                      "Бэктест использовал 25% капитала, а виртуальные счета — 10%.\n",
                      encoding="utf-8")
    return activation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--strategy-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(activate(args.review, args.strategy_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
