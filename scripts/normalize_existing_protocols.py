"""Record the exact observed variant grid for older complete monthly runs.

This is an ex-post structural reconstruction, never evidence that the grid was
frozen before the original run. Missing pairs remain explicit skips.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.research.timeframes import source_path
SNAPSHOT = "data/candles/moex_scan/universe_2026-10-30.json"
TARGETS = (
    "double-indicator/ema-efficiency-monthly",
    "double-indicator/ema25-higher-timeframe-lines",
    "double-indicator/weekly-trendlines-volume-profile",
    "single-indicator/htf-level-breakouts",
    "three-trader-rules",
    "turtle/period-grid",
)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def normalize(name: str) -> None:
    folder = ROOT / "experiments" / name
    protocol_path = folder / "protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    results = folder / "results"
    rows = read_csv(results / "all_variants.csv")
    observed = {(row["symbol"], row["timeframe"]) for row in rows}
    variants = sorted({row["variant"] for row in rows})
    if "baseline" in variants:
        variants.remove("baseline")
        variants.insert(0, "baseline")
    protocol["expected_variants"] = variants
    if not protocol.get("parameter_grid"):
        if name == "turtle/period-grid":
            protocol["parameter_grid"] = {
                "axes": {"entry": {"values": protocol["entry_lengths"]},
                         "exit": {"values": protocol["exit_lengths"]}},
                "less_than": [["exit", "entry"]],
                "variant_template": "dennis_turtle_{entry}_{exit}",
                "include_baseline": True,
                "max_combinations": len(protocol["entry_lengths"]) * len(protocol["exit_lengths"]),
            }
            protocol["parameter_grid_provenance"] = "reconstructed_from_original_protocol_axes"
        else:
            protocol["parameter_grid"] = {
                "axes": {"variant": {"values": variants[1:]}},
                "variant_template": "{variant}",
                "include_baseline": True,
                "max_combinations": len(variants),
            }
            protocol["parameter_grid_provenance"] = "ex_post_inventory_of_observed_variants_not_preregistered"
    if not protocol.get("eligible_universe"):
        selected = protocol.get("symbols")
        protocol["eligible_universe"] = {
            "snapshot_file": SNAPSHOT,
            "cache_dir": "data/candles/moex_scan",
            "board": "TQBR",
            "requires_source_timeframes": ["1D", "1H"],
            **({"symbols": selected} if isinstance(selected, list) else {}),
        }
        protocol["eligible_universe_provenance"] = (
            "original_explicit_symbols" if isinstance(selected, list) else
            "frozen_snapshot_board_and_candle_availability")
    protocol.setdefault("primary_evaluation", "monthly")
    protocol.setdefault("late_sample_status", "seen_history")
    protocol_path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")

    skipped_path = results / "skipped.csv"
    if not skipped_path.exists():
        inventory = json.loads((ROOT / SNAPSHOT).read_text(encoding="utf-8"))
        selected = set(protocol["eligible_universe"].get("symbols", []))
        eligible = {item["SECID"] for item in inventory if item.get("BOARDID") == "TQBR"
                    and (not selected or item["SECID"] in selected)
                    and all(source_path(ROOT / "data/candles/moex_scan", item["SECID"], frame).exists()
                            for frame in ("1D", "1H"))}
        # File layout is checked by the validator; skip rows here only record
        # pairs absent from the original result, without claiming a cause.
        omissions = sorted((symbol, frame) for symbol in eligible
                           for frame in protocol["signal_timeframes"]
                           if (symbol, frame) not in observed)
        with skipped_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("symbol", "timeframe", "reason"))
            writer.writeheader()
            writer.writerows({"symbol": symbol, "timeframe": frame,
                              "reason": "not_evaluated_in_original_run; cause_unverified"}
                             for symbol, frame in omissions)
    print(name, len(rows), len(variants), flush=True)


if __name__ == "__main__":
    for target in TARGETS:
        normalize(target)
