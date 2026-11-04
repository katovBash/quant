"""Validate a frozen, per-account paper trading setup."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path


FIELDS = {"account_id", "symbol", "strategy", "timeframe", "initial_capital_rub",
          "position_weight_pct", "mode", "lot_size_shares", "fee_bps", "slip_bps",
          "borrow_bps_annual", "stop_loss_pct"}


def load_setup(path: Path, strategy_id: str | None = None) -> dict:
    setup = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(setup, dict) or set(setup) != FIELDS:
        raise ValueError(f"setup must contain exactly: {', '.join(sorted(FIELDS))}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", setup["account_id"]):
        raise ValueError("invalid account_id")
    if not re.fullmatch(r"[A-Z0-9]+", setup["symbol"]):
        raise ValueError("invalid symbol")
    if not isinstance(setup["strategy"], str) or not setup["strategy"]:
        raise ValueError("invalid strategy")
    if strategy_id is not None and setup["strategy"] != strategy_id:
        raise ValueError("strategy does not match expected rule")
    if setup["timeframe"] not in ("1H", "4H", "1D"):
        raise ValueError("this runner supports only 1H, 4H and 1D strategies")
    if setup["mode"] not in ("long", "short", "long_short"):
        raise ValueError("invalid mode")
    for key in ("initial_capital_rub", "position_weight_pct", "fee_bps", "slip_bps", "borrow_bps_annual"):
        value = setup[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(f"invalid {key}")
    if setup["initial_capital_rub"] <= 0 or not 0 < setup["position_weight_pct"] <= 100:
        raise ValueError("capital must be positive and position weight in (0, 100]")
    if any(setup[key] < 0 for key in ("fee_bps", "slip_bps", "borrow_bps_annual")):
        raise ValueError("costs must be nonnegative")
    if isinstance(setup["lot_size_shares"], bool) or not isinstance(setup["lot_size_shares"], int) or setup["lot_size_shares"] < 1:
        raise ValueError("lot size must be a positive integer")
    if setup["stop_loss_pct"] is not None:
        raise ValueError("stop_loss_pct is not implemented; keep null until its execution model is tested")
    return setup
