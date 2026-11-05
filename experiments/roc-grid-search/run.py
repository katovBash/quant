"""Rebuild the archived grid from frozen candles, including monthly equity."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.rebuild_legacy_months import rebuild

if __name__ == "__main__":
    print(rebuild(Path(__file__).resolve().parent))
