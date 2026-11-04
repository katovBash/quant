"""Rebuild REPORT.md and monthly_case_summary.csv from saved experiment results."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.research.experiment_report import build_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    summary = json.loads((args.results / "summary.json").read_text(encoding="utf-8"))
    with (args.results / "all_variants.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    with (args.results / "monthly_returns.csv").open(newline="", encoding="utf-8-sig") as stream:
        monthly_rows = list(csv.DictReader(stream))
    build_report(args.results, protocol, summary, rows, monthly_rows)
    print(args.results / "REPORT.md")


if __name__ == "__main__":
    main()
