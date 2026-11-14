"""Compare the paper adapter with the frozen experiment signals on saved candles."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.research.sma_band_close_breakout import signals_for_variant
from src.research.timeframes import load_research_bars
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, VARIANT, signal


def check() -> dict:
    checked = events = mismatches = 0
    by_symbol = {}
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        entries, _ = signals_for_variant(VARIANT, bars)
        signal_indices = [i for i, entry in enumerate(entries) if entry]
        indices = set(signal_indices[-60:])
        indices.update(range(max(0, len(bars) - 20), len(bars)))
        symbol_mismatches = 0
        for i in sorted(indices):
            expected = "long" if entries[i] > 0 else "short" if entries[i] < 0 else None
            symbol_mismatches += signal(bars[:i + 1]) != expected
            checked += 1
            events += bool(entries[i])
        mismatches += symbol_mismatches
        by_symbol[symbol] = {"bars_checked": len(indices), "mismatches": symbol_mismatches}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "paper adapter on historical prefixes versus frozen experiment entry series",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": checked, "signal_events_checked": events,
              "mismatches": mismatches, "symbols": by_symbol}
    Path(__file__).with_name("parity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    outcome = check()
    print(json.dumps({k: outcome[k] for k in ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if outcome["mismatches"] else 0)
