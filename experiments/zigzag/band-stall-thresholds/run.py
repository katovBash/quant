"""Run the preregistered extreme-stall grid on the frozen OHLCV universe."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stall_signals import context_factory
from src.research.trader_method_run import run


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        context_factory=context_factory)
