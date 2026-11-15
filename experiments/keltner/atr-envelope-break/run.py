"""Full-universe preregistered classic-indicator experiment."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.research.trader_method_run import run
from src.research.classic_indicator_grid import signals_for_method
METHOD = "keltner"
if __name__ == "__main__":
    run(Path(__file__).resolve().parent, smoke="--smoke" in sys.argv,
        signal_factory=lambda variant, bars: signals_for_method(METHOD, variant, bars))
