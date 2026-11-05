"""Shared numeric criteria for experiment selection and paper review."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_policy() -> dict:
    path = Path(__file__).with_name("POLICY.json")
    policy = json.loads(path.read_text(encoding="utf-8"))
    experiment = policy["experiment"]
    paper = policy["paper"]
    if (experiment["min_eligible_symbols_for_broad_test"] < experiment["paper_stock_count"]
            or experiment["paper_stock_count"] < 1
            or not 0 < experiment["liquidity_top_fraction"] <= 1
            or experiment["min_train_months_per_pair_for_ranking"] < 1
            or experiment["min_late_months_per_pair_for_diagnostics"] < 1
            or paper["first_review_after_calendar_days"] < 1
            or paper["real_orders_enabled"] is not False):
        raise ValueError("invalid guardrails/POLICY.json")
    return policy
