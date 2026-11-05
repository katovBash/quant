"""Run the preregistered confirmed-swing Fibonacci retracement grid."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.research.fibonacci_signals import retracement_signals
from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run
import json

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
assert PROTOCOL["expected_variants"] == variants_from_grid(PROTOCOL["parameter_grid"])


def signal_factory(variant, bars):
    _, wing, ratio, tolerance = variant.split("_")
    return retracement_signals(bars, int(wing), float(ratio), float(tolerance))


if __name__ == "__main__":
    run(HERE, smoke="--smoke" in sys.argv, signal_factory=signal_factory)
