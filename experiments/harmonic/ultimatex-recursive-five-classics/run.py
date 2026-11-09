from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.research.harmonic_recursive_proxy import (
    KINDS, detect_from_events, pivot_events, union_patterns,
)
from src.research.harmonic_ultimatex_proxy import pattern_signals
from src.research.trader_method_run import run


_bars = None
_events = {}
_patterns = {}


def signal_factory(variant, bars):
    global _bars
    if _bars is not bars:
        _bars = bars
        _events.clear()
        _patterns.clear()
    kind, level_text, wing_text = variant.split("_")
    level, wing = int(level_text[1:]), int(wing_text[1:])
    event_key = (level, wing)
    if event_key not in _events:
        _events[event_key] = pivot_events(bars, wing, level)

    def for_kind(one_kind):
        key = (one_kind, level, wing)
        if key not in _patterns:
            _patterns[key] = detect_from_events(_events[event_key], one_kind)
        return _patterns[key]

    patterns = (union_patterns({one: for_kind(one) for one in KINDS}) if kind == "union"
                else for_kind(kind))
    return pattern_signals(bars, patterns, "detect", "time20")


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=signal_factory)
