from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.research.trader_method_run import run
if __name__ == '__main__':
    run(Path(__file__).resolve().parent, smoke='--smoke' in sys.argv)
