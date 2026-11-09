"""Full-universe 1D support/resistance bounce and target comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run
from src.research.zigzag_signals import third_touch_signals

EXPERIMENT = Path(__file__).resolve().parent
PRESETS = {"a": (3, 2.0, 0.5, 50), "b": (5, 4.0, 1.0, 100)}
EXITS = {"op": "opposite_signal", "t5": "tp_5", "t8": "tp_8",
         "a2": "tp_atr_2", "a4": "tp_atr_4"}


def signals(variant: str, bars: list[dict]):
    kind, preset, slope, target = variant.split("_")
    if kind not in ("c", "d") or preset not in PRESETS or slope not in ("any", "trend"):
        raise ValueError(f"unknown variant: {variant}")
    if (kind == "c") != (target == "op") or target not in EXITS:
        raise ValueError(f"invalid target/control: {variant}")
    return third_touch_signals(bars, *PRESETS[preset], "bounce",
                               exit_mode=EXITS[target], slope_mode=slope)


def main() -> None:
    protocol = json.loads((EXPERIMENT / "protocol.json").read_text(encoding="utf-8"))
    if protocol["expected_variants"] != variants_from_grid(protocol["parameter_grid"]):
        raise ValueError("protocol grid differs from expected variants")
    run(EXPERIMENT, smoke="--smoke" in sys.argv, signal_factory=signals)


if __name__ == "__main__":
    main()
