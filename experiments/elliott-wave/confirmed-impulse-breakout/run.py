"""Full-universe causal Elliott impulse proxy experiment."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.elliott_signals import impulse_breakout_signals
from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run

HERE = Path(__file__).resolve().parent
PROTOCOL = json.loads((HERE / "protocol.json").read_text(encoding="utf-8"))
if variants_from_grid(PROTOCOL["parameter_grid"]) != PROTOCOL["expected_variants"]:
    raise ValueError("protocol parameter grid differs from expected variants")


def signal_factory(variant: str, bars: list[dict]):
    pattern, wing, deviation = variant.split("_")
    return impulse_breakout_signals(bars, pattern, int(wing), float(deviation))


if __name__ == "__main__":
    result = run(HERE, smoke="--smoke" in sys.argv, signal_factory=signal_factory)
    print(json.dumps({"symbols": result["symbols"], "rows": result["rows"],
                      "months": result["months"], "errors": len(result["errors"])},
                     ensure_ascii=False))
