"""Compare the daily-fed paper adapter with frozen weekly experiment signals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.research.band_zigzag_weekly import signals_for_variant
from datetime import date

from src.research.timeframes import aggregate_weeks, load_research_bars
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, VARIANT, signal


def check() -> dict:
    cache = ROOT / "data/candles/moex_scan"
    mismatches = bars_checked = signals_checked = 0
    details = {}
    examples = []
    for symbol in PAPER_SYMBOLS:
        daily = load_research_bars(cache, symbol, "1D")
        weeks = aggregate_weeks(daily)
        entries, _ = signals_for_variant(VARIANT, weeks)
        expected_by_date = {bar["ts"][:10]: ("long" if entry > 0 else
                              "short" if entry < 0 else None)
                            for bar, entry in zip(weeks, entries)}
        symbol_mismatches = symbol_events = 0
        for index in range(1, len(daily)):
            day = daily[index]["ts"][:10]
            previous_day = daily[index - 1]["ts"][:10]
            if date.fromisoformat(day).isocalendar()[:2] == date.fromisoformat(previous_day).isocalendar()[:2]:
                continue
            finalized = aggregate_weeks(daily[:index])
            week_end = finalized[-1]["ts"][:10]
            expected = expected_by_date.get(week_end)
            actual = signal(finalized)
            bars_checked += 1
            symbol_events += bool(expected)
            if expected != actual:
                symbol_mismatches += 1
                if len(examples) < 20:
                    examples.append({"symbol": symbol, "week_end": week_end,
                                     "next_week_first_bar": day,
                                     "expected": expected, "actual": actual})
        signals_checked += symbol_events
        mismatches += symbol_mismatches
        details[symbol] = {"week_transitions": sum(date.fromisoformat(daily[i]["ts"][:10]).isocalendar()[:2] !=
                                                         date.fromisoformat(daily[i-1]["ts"][:10]).isocalendar()[:2]
                                                         for i in range(1, len(daily))),
                           "signal_events": symbol_events,
                           "mismatches": symbol_mismatches}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT,
              "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "paper next-week transition vs frozen completed-week signal series",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": bars_checked,
              "signal_events_checked": signals_checked,
              "mismatches": mismatches, "symbols": details,
              "mismatch_examples": examples,
              "note": "A week is finalized only when the first completed daily candle of the next ISO week is observed, so Saturday sessions are included. The paper order is backdated to that day's opening price on replay."}
    (HERE / "parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in
                      ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
