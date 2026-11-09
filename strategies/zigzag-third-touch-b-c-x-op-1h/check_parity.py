"""Compare the fixed paper adapter with frozen 1H experiment signals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from src.research.zigzag_signals import third_touch_signals
from strategy import (DEVIATION_PCT, MAX_AGE, PAPER_SYMBOLS, STRATEGY_ID,
                      TIMEFRAME, WING, ZONE_PCT, signal)

VARIANT = "z3_b_c_x_op"
SOURCE = ROOT / "data/candles/moex_scan"


def check() -> dict:
    bars_checked = signal_events = mismatches = 0
    by_symbol = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(SOURCE, symbol, TIMEFRAME)
        entries, _ = third_touch_signals(bars, WING, DEVIATION_PCT, ZONE_PCT,
                                         MAX_AGE, "breakout", exit_mode="opposite_signal")
        event_indices = [index for index, entry in enumerate(entries) if entry]
        indices = set(event_indices[-50:])
        for index in range(len(bars) - 1, -1, -1):
            if len(indices) >= 100:
                break
            indices.add(index)
        count = len(indices)
        symbol_mismatches = 0
        for index in sorted(indices):
            actual = signal(bars[:index + 1])
            expected = "long" if entries[index] > 0 else "short" if entries[index] < 0 else None
            bars_checked += 1
            signal_events += expected is not None
            if actual != expected:
                symbol_mismatches += 1
        mismatches += symbol_mismatches
        by_symbol[symbol] = {"bars_checked": count, "mismatches": symbol_mismatches}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "paper adapter on each historical prefix versus frozen experiment signal series",
              "independent_signal_implementation": False,
              "bars_checked": bars_checked, "signal_events_checked": signal_events,
              "mismatches": mismatches, "symbols": by_symbol}
    (Path(__file__).with_name("parity.json")).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    outcome = check()
    print(json.dumps({key: outcome[key] for key in ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if outcome["mismatches"] else 0)
