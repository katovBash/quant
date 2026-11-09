"""Check the fixed paper adapter on every selected symbol's historical prefixes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from src.research.zigzag_signals import confirmed_channel_bounce_signals
from strategy import (DEVIATION_PCT, MAX_AGE, PAPER_SYMBOLS, STRATEGY_ID,
                      TIMEFRAME, WING, ZONE_PCT, signal)

VARIANT = "ch_a_inside_op"
SOURCE = ROOT / "data/candles/moex_scan"


def check() -> dict:
    bars_checked = signal_events = mismatches = 0
    by_symbol = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(SOURCE, symbol, TIMEFRAME)
        entries, exits = confirmed_channel_bounce_signals(
            bars, WING, DEVIATION_PCT, ZONE_PCT, MAX_AGE,
            exit_mode="opposite_line", confirm_mode="inside")
        indices = set(i for i, (entry, exit_) in enumerate(zip(entries, exits))
                      if entry or exit_)
        indices.update(range(max(0, len(bars) - 100), len(bars)))
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
              "method": "paper adapter on historical prefixes versus experiment signal series",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": bars_checked, "signal_events_checked": signal_events,
              "mismatches": mismatches, "symbols": by_symbol}
    (HERE / "parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in
                      ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
