from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.research.harmonic_ultimatex_proxy import detect_patterns, pattern_signals
from src.research.trader_method_run import run


_cache = {}
_cache_bars = None


def signal_factory(variant, bars):
    global _cache_bars
    kind, wing, entry, exit_mode = variant.split("_")
    wing = int(wing[1:])
    if _cache_bars is not bars:
        _cache.clear()
        _cache_bars = bars
    key = (kind, wing)
    if key not in _cache:
        _cache[key] = detect_patterns(bars, wing, kind)
    return pattern_signals(bars, _cache[key], entry, exit_mode)


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=signal_factory)
