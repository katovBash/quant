"""Full-universe 1H session-VWAP reversion experiment."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.research.hourly_scalping_signals import signals
from src.research.trader_method_run import run


def signal_factory(variant, bars):
    _, deviation, hold = variant.split("_")
    return signals(bars, float(deviation), int(hold))


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=signal_factory)
