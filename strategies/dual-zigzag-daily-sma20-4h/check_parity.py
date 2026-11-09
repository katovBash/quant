"""Measure fixed paper adapter against frozen full-series experiment events."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, VARIANT, events, module


def check():
    checked = signal_events = mismatches = 0
    examples = []
    details = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        accepted, raw = module.factory(symbol, TIMEFRAME)(VARIANT, bars)
        symbol_bad = symbol_events = 0
        for i in range(max(60, len(bars) - 200), len(bars)):
            actual_accepted, actual_raw = events(bars[:i + 1])
            checked += 1
            signal_events += bool(accepted[i]) or bool(raw[i])
            symbol_events += bool(accepted[i]) or bool(raw[i])
            if (accepted[i], raw[i]) != (actual_accepted, actual_raw):
                mismatches += 1
                symbol_bad += 1
                if len(examples) < 20:
                    examples.append({"symbol": symbol, "bar": bars[i]["ts"],
                                     "expected": [accepted[i], raw[i]],
                                     "actual": [actual_accepted, actual_raw]})
        details[symbol] = {"bars_checked": min(200, len(bars) - 60),
                           "signal_events": symbol_events,
                           "mismatches": symbol_bad}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "last 200 completed 4H prefixes per selected stock; entry and raw exit events",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": checked, "signal_events_checked": signal_events,
              "mismatches": mismatches, "symbols": details,
              "mismatch_examples": examples}
    (HERE / "parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in
                      ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
