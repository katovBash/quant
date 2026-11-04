"""Compare fixed SMA12/60 with two past-only sideways filters on SMLT 1H."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from src.ema.core.adx_ema import adx
from src.ema.core.research_ema_combinations import simulate
from src.research.indicator_library import crosses, sma
from src.research.standalone_grid import atr, load_bars

OUT = Path(__file__).resolve().parent / "results/fixed_pair.csv"
PERIODS = (("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"),
           ("2026_to_oct30", "2026-01-01", None),
           ("oct_2026", "2026-10-01", "2026-11-01"),
           ("all_seen_history", "2024-01-01", None))


def hysteresis_signals(fast: list[float], slow: list[float], volatility: list[float],
                       threshold_atr: float) -> list[int]:
    """Switch sides only after SMA separation exceeds the ATR band at close."""
    signals = [0] * len(fast)
    side = 0
    for i, (a, b, v) in enumerate(zip(fast, slow, volatility)):
        if not all(math.isfinite(x) for x in (a, b, v)):
            continue
        spread = a - b
        if spread > threshold_atr * v and side != 1:
            signals[i], side = 1, 1
        elif spread < -threshold_atr * v and side != -1:
            signals[i], side = -1, -1
    return signals


def run() -> list[dict]:
    bars = load_bars("SMLT", "1H")
    closes = [bar["close"] for bar in bars]
    fast, slow = sma(closes, 12), sma(closes, 60)
    base = crosses(fast, slow)
    volatility = atr(bars, 14)
    strength = adx(bars, 14)
    all_allowed = [True] * len(bars)
    variants = (
        ("baseline", base, all_allowed),
        ("adx14_ge_20_entry", base, [math.isfinite(x) and x >= 20 for x in strength]),
        ("adx14_ge_25_entry", base, [math.isfinite(x) and x >= 25 for x in strength]),
        ("atr14_hysteresis_0.10", hysteresis_signals(fast, slow, volatility, 0.10), all_allowed),
        ("atr14_hysteresis_0.25", hysteresis_signals(fast, slow, volatility, 0.25), all_allowed),
        ("atr14_hysteresis_0.50", hysteresis_signals(fast, slow, volatility, 0.50), all_allowed),
    )
    rows = []
    for name, signals, allowed in variants:
        for period, start, end in PERIODS:
            result = simulate(bars, signals, allowed, allowed, 0.2, start, end)
            rows.append({"variant": name, "period": period, "return_pct": result["return_pct"],
                         "closed_trades": result["closed_trades"],
                         "winning_trades": result["winning_trades"],
                         "profit_factor": result["profit_factor"],
                         "max_drawdown_pct": result["max_drawdown_pct"]})
    with OUT.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return rows


if __name__ == "__main__":
    for row in run():
        if row["period"] in ("all_seen_history", "oct_2026"):
            print(row)
