"""Compare the chosen control adapter with frozen EMA-experiment signals."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, VARIANT, signal

SOURCE = ROOT / "experiments/double-indicator/dual-zigzag-ema-support-resistance/run.py"
spec = importlib.util.spec_from_file_location("ema_support_experiment", SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError("EMA experiment unavailable")
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


def check() -> dict:
    checked = events_checked = mismatches = 0
    details = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        entries, exits = experiment.factory(symbol, TIMEFRAME)(VARIANT, bars)
        indices = range(max(0, len(bars) - 200), len(bars))
        local_mismatches = local_events = 0
        for index in indices:
            entry, raw_exit = entries[index], exits[index]
            local_events += bool(entry or raw_exit)
            for position in (-1, 0, 1):
                expected = ("long" if entry > 0 else "short" if entry < 0 else
                            "flat" if raw_exit > 0 and position < 0 else None)
                if signal(bars[:index + 1], position=position) != expected:
                    local_mismatches += 1
            checked += 1
        events_checked += local_events
        mismatches += local_mismatches
        details[symbol] = {"bars_checked": len(indices), "signal_events": local_events,
                           "mismatches": local_mismatches}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "latest 200 completed 4H prefixes per selected stock against frozen experiment entry/exit arrays",
              "independent_signal_implementation": False, "pine_verified_against_python": False,
              "bars_checked": checked, "signal_events_checked": events_checked,
              "mismatches": mismatches, "symbols": details}
    (HERE / "parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in
                      ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
