"""Compare every selected stock's paper signal with frozen experiment events."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.research.timeframes import load_research_bars
from strategy import PAPER_SYMBOLS, STRATEGY_ID, TIMEFRAME, signal


def source_signals(bars: list[dict]) -> tuple[list[int], list[int]]:
    source = ROOT / "experiments/turtle/period-grid/signals.py"
    spec = importlib.util.spec_from_file_location("turtle_experiment_signals", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen experiment signals")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    extrema = module.prior_extrema(bars, {20, 30})
    return module.turtle_from_extrema(bars, 30, 20, extrema)


def check() -> dict:
    checked = 0
    mismatches = []
    for symbol in PAPER_SYMBOLS:
        bars = load_research_bars(ROOT / "data/candles/moex_scan", symbol, TIMEFRAME)
        entries, exits = source_signals(bars)
        for index in range(30, len(bars)):
            for position in (-1, 0, 1):
                raw = entries[index]
                expected = ("long" if raw > 0 else "short" if raw < 0 else
                            "flat" if position > 0 and exits[index] < 0 else
                            "flat" if position < 0 and exits[index] > 0 else None)
                actual = signal(bars[:index + 1], position=position)
                checked += 1
                if actual != expected:
                    mismatches.append({"symbol": symbol, "bar": index,
                                       "position": position, "expected": expected,
                                       "actual": actual})
    return {"strategy_id": STRATEGY_ID, "variant": "dennis_turtle_30_20",
            "timeframe": TIMEFRAME, "bars_checked": checked,
            "mismatches": len(mismatches), "examples": mismatches[:10],
            "source": "experiments/turtle/period-grid/signals.py on frozen MOEX 1D candles"}


if __name__ == "__main__":
    result = check()
    (Path(__file__).parent / "parity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if not result["mismatches"] else 1)
