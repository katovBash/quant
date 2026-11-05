"""One-command structural validation and report regeneration for a completed experiment."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.corporate_actions import load_dividend_snapshot
from src.research.experiment_report import build_report
from src.research.monthly_validation import validate_monthly_rows
from src.research.timeframes import source_path
from src.research.parameter_grid import variants_from_grid
from src.research.combination_review import audit as combination_audit
from guardrails.policy import load_policy

from check_coverage import check


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def validate(protocol_path: Path, results: Path, min_symbols: int = 0) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    rows = read_csv(results / "all_variants.csv")
    months = read_csv(results / "monthly_returns.csv")
    monthly_check = validate_monthly_rows(months)
    coverage = check(results / "all_variants.csv", protocol["signal_timeframes"],
                     min_symbols, results / "monthly_returns.csv")
    actual_variants = {row["variant"] for row in rows}
    expected_variants = set(protocol.get("expected_variants", []))
    if protocol.get("parameter_grid"):
        generated = set(variants_from_grid(protocol["parameter_grid"]))
        if expected_variants and generated != expected_variants:
            raise ValueError("expected_variants disagrees with parameter_grid")
        expected_variants = generated
    grid_check = {"expected": len(expected_variants), "actual": len(actual_variants),
                  "missing": sorted(expected_variants - actual_variants),
                  "unexpected": sorted(actual_variants - expected_variants),
                  "ok": bool(expected_variants) and actual_variants == expected_variants}
    combination_check = combination_audit(protocol, rows)
    universe_spec = protocol.get("eligible_universe") or {}
    universe_check = {"eligible_symbols": 0, "covered_pairs": 0, "missing_pairs": [], "ok": False}
    if universe_spec:
        inventory = json.loads((ROOT / universe_spec["snapshot_file"]).read_text(encoding="utf-8"))
        cache = ROOT / universe_spec["cache_dir"]
        required_sources = universe_spec["requires_source_timeframes"]
        eligible = {item["SECID"] for item in inventory
                    if (not universe_spec.get("board") or item.get("BOARDID") == universe_spec["board"])
                    and all(source_path(cache, item["SECID"], frame).exists()
                            for frame in required_sources)}
        if universe_spec.get("symbols"):
            eligible &= set(universe_spec["symbols"])
        observed = {(row["symbol"], row["timeframe"]) for row in rows}
        skipped = read_csv(results / "skipped.csv") if (results / "skipped.csv").exists() else []
        omitted = {(item["symbol"], frame) for item in skipped
                   for frame in (protocol["signal_timeframes"] if item["timeframe"] == "all"
                                 else [item["timeframe"]])}
        expected_pairs = {(symbol, frame) for symbol in eligible
                          for frame in protocol["signal_timeframes"]}
        missing = sorted(expected_pairs - observed - omitted)
        universe_check = {"eligible_symbols": len(eligible),
                          "covered_pairs": len(expected_pairs - set(missing)),
                          "missing_pairs": [list(pair) for pair in missing],
                          "ok": not missing}
    by_pair: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in months:
        by_pair[(item["symbol"], item["timeframe"], item["variant"])].append(item)
    period_counts = {"pairs": len(by_pair), "with_2_full_months": 0,
                     "with_2_calendar_years": 0, "with_train_and_late": 0,
                     "with_last_1m": 0, "with_last_3m": 0,
                     "with_last_6m": 0, "with_last_9m": 0, "with_last_12m": 0}
    for pair_months in by_pair.values():
        ordered = sorted(pair_months, key=lambda item: item["start"])
        period_counts["with_2_full_months"] += len(ordered) >= 2
        period_counts["with_2_calendar_years"] += len({item["start"][:4] for item in ordered}) >= 2
        samples = {item.get("sample") for item in ordered}
        period_counts["with_train_and_late"] += ("train" in samples and any(
            isinstance(sample, str) and sample.startswith("late") for sample in samples))
        for length in (1, 3, 6, 9, 12):
            tail = ordered[-length:]
            try:
                indices = [int(item["start"][:4]) * 12 + int(item["start"][5:7]) for item in tail]
                contiguous = len(tail) == length and all(b - a == 1 for a, b in zip(indices, indices[1:]))
            except ValueError:
                contiguous = False
            period_counts[f"with_last_{length}m"] += contiguous
    corporate = protocol.get("corporate_actions", {})
    corporate_status = corporate.get("status", "unchecked")
    corporate_check = {"status": corporate_status,
                       "applied_in_main_results": bool(corporate.get("applied_in_main_results")),
                       "splits_status": corporate.get("splits_status", "unchecked"),
                       "covered_symbols": 0, "verified_snapshot_sha256": None}
    source_status_file = ROOT / "data/dividends/moex_coverage.json"
    if source_status_file.is_file():
        source_status = json.loads(source_status_file.read_text(encoding="utf-8"))
        corporate_check["moex_source_status"] = source_status.get("status", "UNKNOWN")
        corporate_check["moex_source_checked_at_utc"] = source_status.get("checked_at_utc")
    if corporate.get("cash_dividend_snapshot"):
        snapshot, digest = load_dividend_snapshot(ROOT / corporate["cash_dividend_snapshot"])
        corporate_check["verified_snapshot_sha256"] = digest
        corporate_check["covered_symbols"] = len({row["symbol"] for row in rows}
                                                  & set(snapshot["covered_symbols"]))
        corporate_check["all_symbols_covered"] = {row["symbol"] for row in rows} <= set(snapshot["covered_symbols"])
    else:
        corporate_check["all_symbols_covered"] = False
    if corporate_status == "complete" and not (corporate_check["all_symbols_covered"]
                                                 and corporate_check["applied_in_main_results"]
                                                 and corporate_check["splits_status"] == "verified"):
        raise ValueError("complete corporate-action status requires covered symbols, applied dividends and verified splits")
    structural_ok = (coverage["ok"] and grid_check["ok"] and combination_check["ok"]
                     and bool(protocol.get("parameter_grid"))
                     and universe_check["ok"]
                     and monthly_check["ok"]
                     and period_counts["with_2_full_months"] == len(by_pair))
    data_ready = (structural_ok and monthly_check["continuous"]
                  and universe_check["eligible_symbols"] >= load_policy()["experiment"]["min_eligible_symbols_for_broad_test"]
                  and corporate_status == "complete"
                  and corporate_check["all_symbols_covered"]
                  and corporate_check["applied_in_main_results"]
                  and corporate_check["splits_status"] == "verified"
                  and period_counts["with_train_and_late"] == len(by_pair))
    result = {"structural_ok": structural_ok,
              "policy_version": load_policy()["version"],
              "status": "DATA_READY" if data_ready else "REVIEW_ONLY",
              "coverage": coverage, "parameter_grid": grid_check,
              "combination": combination_check,
              "universe": universe_check, "periods": period_counts,
              "monthly_validation": monthly_check,
              "corporate_actions": corporate_check,
              "note": "DATA_READY confirms data and report gates only; it does not approve a trading strategy."}
    # A report remains useful when the completeness gate fails: show the
    # observed months and the failed validation side by side.
    if rows and months:
        build_report(results, protocol, summary, rows, months)
        if not structural_ok:
            report = results / "REPORT.md"
            body = report.read_text(encoding="utf-8")
            report.write_text(
                "> **REVIEW_ONLY:** проверка структуры не пройдена. "
                "Числа ниже приведены для разбора, не для выбора стратегии. "
                "Причины: [validation.json](validation.json).\n\n" + body,
                encoding="utf-8")
    (results / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--min-symbols", type=int, default=0)
    args = parser.parse_args()
    result = validate(args.protocol, args.results, args.min_symbols)
    print(json.dumps({"status": result["status"], "structural_ok": result["structural_ok"],
                      "parameter_grid": result["parameter_grid"], "universe": result["universe"],
                      "periods": result["periods"],
                      "monthly_validation": result["monthly_validation"],
                      "corporate_actions": result["corporate_actions"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["structural_ok"] else 1)


if __name__ == "__main__":
    main()
