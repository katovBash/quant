"""Measured paper adapter parity on frozen source prefixes."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.timeframes import load_research_bars
from src.research.classic_indicator_grid import signals_for_method
from strategy import STRATEGY_ID, TIMEFRAME, VARIANT, PAPER_SYMBOLS, signal
def check():
    checked = events = mismatches = 0
    by_symbol = {}
    family = VARIANT.split("_", 1)[0]
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        entries, _ = signals_for_method(family, VARIANT, bars)
        event_indices = [i for i, value in enumerate(entries) if value]
        step = max(1, len(event_indices) // 40)
        indices = set(event_indices[::step])
        indices.update(range(max(0, len(bars) - 40), len(bars)))
        stride = max(1, len(bars) // 80)
        indices.update(range(0, len(bars), stride))
        symbol_mismatch = 0
        for index in sorted(indices):
            expected = "long" if entries[index] > 0 else "short" if entries[index] < 0 else None
            symbol_mismatch += signal(bars[:index + 1]) != expected
            checked += 1
            events += bool(entries[index])
        mismatches += symbol_mismatch
        by_symbol[symbol] = {"bars_checked": len(indices), "mismatches": symbol_mismatch}
    result = {"strategy_id": STRATEGY_ID, "variant": VARIANT, "timeframe": TIMEFRAME,
              "source": "MOEX ISS local snapshot 2026-10-30",
              "method": "paper adapter on historical prefixes versus frozen experiment entry series",
              "independent_signal_implementation": False,
              "pine_verified_against_python": False,
              "bars_checked": checked, "signal_events_checked": events,
              "mismatches": mismatches, "symbols": by_symbol}
    Path(__file__).with_name("parity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result
if __name__ == "__main__":
    result = check()
    print(json.dumps({key: result[key] for key in ("bars_checked", "signal_events_checked", "mismatches")}))
    raise SystemExit(1 if result["mismatches"] else 0)
