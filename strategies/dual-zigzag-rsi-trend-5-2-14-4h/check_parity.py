"""Compare paper prefix decisions with the frozen experiment signal series."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, VARIANT, module, signal


def check():
    checked = events = mismatches = 0
    examples = []
    by_symbol = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        expected, _ = module.factory(symbol, TIMEFRAME)(VARIANT, bars)
        symbol_mismatches = symbol_events = 0
        for i in range(max(30, len(bars) - 200), len(bars)):
            want = "long" if expected[i] > 0 else "short" if expected[i] < 0 else None
            got = signal(bars[:i + 1])
            checked += 1
            symbol_events += bool(want)
            if got != want:
                mismatches += 1
                symbol_mismatches += 1
                if len(examples) < 20:
                    examples.append({"symbol": symbol, "bar": bars[i]["ts"],
                                     "expected": want, "actual": got})
        events += symbol_events
        by_symbol[symbol] = {"bars_checked": min(200, len(bars) - 30),
                             "signal_events": symbol_events,
                             "mismatches": symbol_mismatches}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "latest 200 completed 4H prefixes per selected stock versus frozen full-series signals",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": checked, "signal_events_checked": events,
              "mismatches": mismatches, "symbols": by_symbol,
              "mismatch_examples": examples}
    (HERE / "parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in
                      ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
