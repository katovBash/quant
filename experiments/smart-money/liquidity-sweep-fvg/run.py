"""Full-universe causal Smart Money sweep + FVG experiment."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.research.smart_money_signals import all_variants
from src.research.trader_method_run import run

_cached_bars = None
_cached_rules = None


def signal_factory(variant, bars):
    global _cached_bars, _cached_rules
    if bars is not _cached_bars:
        _cached_bars, _cached_rules = bars, all_variants(bars)
    return _cached_rules[variant]


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=signal_factory)
