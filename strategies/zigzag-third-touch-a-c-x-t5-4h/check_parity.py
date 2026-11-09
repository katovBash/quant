"""Compare the 4H paper adapter with frozen third-touch experiment events."""

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

VARIANT = "z3_a_c_x_t5"
SOURCE = ROOT / "data/candles/moex_scan"


def check() -> dict:
    bars_checked = signal_events = mismatches = 0
    by_symbol = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(SOURCE, symbol, TIMEFRAME)
        entries, exits = third_touch_signals(bars, WING, DEVIATION_PCT,
                                             ZONE_PCT, MAX_AGE, "breakout", exit_mode="tp_5")
        events = [index for index, (entry, exit_) in enumerate(zip(entries, exits))
                  if entry or exit_]
        indices = set(events[-60:])
        for index in range(len(bars) - 1, -1, -1):
            if len(indices) >= 100:
                break
            indices.add(index)
        symbol_mismatches = 0
        for index in sorted(indices):
            entry, exit_ = entries[index], exits[index]
            signal_events += bool(entry or exit_)
            for position in (-1, 0, 1):
                expected = ("long" if entry > 0 else "short" if entry < 0 else
                            "flat" if (position > 0 and exit_ < 0) or
                                      (position < 0 and exit_ > 0) else None)
                if signal(bars[:index + 1], position=position) != expected:
                    symbol_mismatches += 1
            bars_checked += 1
        mismatches += symbol_mismatches
        by_symbol[symbol] = {"bars_checked": len(indices), "mismatches": symbol_mismatches}
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
