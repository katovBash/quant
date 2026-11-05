"""Check MOEX CCI dividend access and save only traceable raw pages when available."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.moex_dividend_source import ENDPOINT, DividendSourceUnavailable, fetch_page

DEFAULT_UNIVERSE = ROOT / "data/candles/moex_scan/universe_2026-10-30.json"
DEFAULT_OUTPUT = ROOT / "data/dividends"


def inspect(universe: Path = DEFAULT_UNIVERSE, output: Path = DEFAULT_OUTPUT,
            *, download: bool = False, cookie: str | None = None) -> dict:
    items = json.loads(universe.read_text(encoding="utf-8"))
    symbols = sorted({item["SECID"] for item in items if item.get("SECID")})
    now = datetime.now(timezone.utc).isoformat()
    try:
        universe_label = str(universe.resolve().relative_to(ROOT))
    except ValueError:
        universe_label = str(universe)
    status = {"checked_at_utc": now, "source": ENDPOINT,
              "universe": universe_label, "universe_symbols": len(symbols),
              "verified_symbols": 0, "applied_in_results": False}
    try:
        first = fetch_page(cookie=cookie)
        if not download:
            status["status"] = "ACCESS_OK_NOT_DOWNLOADED"
            status["blocks"] = list(first)
        else:
            # The paid response schema cannot be verified without subscription.
            # Preserve the exchange's raw data, never silently map unknown fields.
            output.mkdir(parents=True, exist_ok=True)
            target = output / ("moex_cci_raw_" + now[:10] + ".json")
            target.write_text(json.dumps({"source": ENDPOINT, "fetched_at_utc": now,
                                          "page_start_0": first}, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
            status["status"] = "RAW_FIRST_PAGE_SCHEMA_REVIEW"
            status["raw_file"] = str(target)
    except DividendSourceUnavailable as exc:
        status["status"] = str(exc)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        status["status"] = "SOURCE_ERROR"
        status["error"] = type(exc).__name__ + ": " + str(exc)
    output.mkdir(parents=True, exist_ok=True)
    (output / "moex_coverage.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    result = inspect(args.universe, args.output, download=args.download,
                     cookie=os.environ.get("MOEX_ISS_COOKIE"))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
