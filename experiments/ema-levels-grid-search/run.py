"""Sweep one EMA as dynamic support or resistance; no EMA cross."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.research.standalone_grid import run


if __name__ == "__main__":
    run("ema_levels")
