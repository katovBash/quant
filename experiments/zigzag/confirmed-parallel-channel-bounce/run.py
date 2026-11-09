"""Full-universe daily ZigZag channel rejection with fixed control."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run
from src.research.zigzag_signals import (confirmed_channel_bounce_signals,
                                        third_touch_signals)

EXPERIMENT = Path(__file__).resolve().parent
PRESETS = {"a": (3, 2.0, 0.5, 80), "b": (5, 4.0, 1.0, 120)}
EXITS = {"t5": "tp_5", "t8": "tp_8", "op": "opposite_line"}


def signals(variant: str, bars: list[dict]):
    if variant == "old_d_a_trend_a4":
        return third_touch_signals(bars, 3, 2.0, 0.5, 50, "bounce",
                                   exit_mode="tp_atr_4", slope_mode="trend")
    prefix, preset, confirm, target = variant.split("_")
    if (prefix != "ch" or preset not in PRESETS or
            confirm not in ("inside", "directional") or target not in EXITS):
        raise ValueError(f"unknown variant: {variant}")
    return confirmed_channel_bounce_signals(
        bars, *PRESETS[preset], exit_mode=EXITS[target], confirm_mode=confirm)


def main() -> None:
    protocol = json.loads((EXPERIMENT / "protocol.json").read_text(encoding="utf-8"))
    if protocol["expected_variants"] != variants_from_grid(protocol["parameter_grid"]):
        raise ValueError("protocol grid differs from expected variants")
    run(EXPERIMENT, smoke="--smoke" in sys.argv, signal_factory=signals)


if __name__ == "__main__":
    main()
