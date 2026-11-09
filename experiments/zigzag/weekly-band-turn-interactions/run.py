"""Full frozen-universe weekly Band-ZigZag turn experiment."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.research.band_zigzag_weekly import signals_for_variant
from src.research.trader_method_run import run


if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=signals_for_variant)
