from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.research.trader_method_run import run
from src.research.zigzag_signals import breakout_signals


def signal_factory(variant, bars):
    _, wing, deviation = variant.split("_")
    return breakout_signals(bars, int(wing), float(deviation))


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=signal_factory)
