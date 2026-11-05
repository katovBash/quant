"""Compare the fixed paper rule with frozen experiment events on selected stocks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from src.research.zigzag_signals import breakout_signals
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, signal


def check() -> dict:
    checked = 0
    mismatches = []
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        entries, exits = breakout_signals(bars, 5, 6)
        # Every historical event, plus a regular sample of neutral bars, on each stock.
        start = 33
        step = max(1, (len(bars) - start) // 150)
        indices = sorted(set(range(start, len(bars), step)) |
                         {i for i in range(start, len(bars)) if entries[i] or exits[i]})
        for index in indices:
            raw = entries[index]
            for position in (-1, 0, 1):
                expected = ("long" if raw > 0 else "short" if raw < 0 else
                            "flat" if position > 0 and exits[index] < 0 else
                            "flat" if position < 0 and exits[index] > 0 else None)
                actual = signal(bars[:index + 1], position=position)
                checked += 1
                if actual != expected:
                    mismatches.append({"symbol": symbol, "bar": index,
                                       "position": position, "expected": expected,
                                       "actual": actual})
    return {"strategy_id": STRATEGY_ID, "variant": "zigzag_5_6",
            "timeframe": TIMEFRAME, "bars_checked": checked,
            "mismatches": len(mismatches), "examples": mismatches[:10],
            "source": "src/research/zigzag_signals.py on frozen MOEX 1D candles",
            "scope": "all experiment events and regularly spaced neutral bars for each selected stock; three position states"}


if __name__ == "__main__":
    result = check()
    (Path(__file__).parent / "parity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["mismatches"] == 0 else 1)
