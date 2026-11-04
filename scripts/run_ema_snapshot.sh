#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD"

python3 -m src.ema.core.scan_ema --from-date 2022-01-01 --to-date 2026-10-30 \
  --timeframes 1D 1W 1M --workers 16
python3 -m src.ema.core.scan_ema --from-date 2024-01-01 --to-date 2026-10-30 \
  --timeframes 1H 4H --limit 50 --workers 12 \
  --out experiments/.history/legacy-ema/12-33-cross/execute/research/intraday
python3 -m src.ema.reports.build_ema_reports
python3 -m src.ema.reports.compare_ema_pairs
python3 -m src.ema.reports.analyze_ema_patterns
python3 -m src.ema.reports.stress_ema
python3 -m unittest discover -s tests -t . -v
