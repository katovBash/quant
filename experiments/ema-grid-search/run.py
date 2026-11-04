"""Sweep EMA periods 2..200 on cached MOEX TQBR equity candles.

The historical snapshot is fixed at 2026-10-30. This does not fetch current data.
Each series is checkpointed independently so interrupted runs can resume.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
EXPERIMENT = Path(__file__).resolve().parent
CACHE = ROOT / "data/moex_scan"
UNIVERSE = ROOT / "data/moex_scan/universe_2026-10-30.json"
HEADER = ("symbol,timeframe,fast,slow,mode,bars,closed_trades,winning_trades,"
          "net_return_pct,buy_hold_return_pct,profit_factor,max_drawdown_pct,"
          "oos_trades,oos_winning_trades,oos_return_pct,oos_buy_hold_pct,"
          "oos_profit_factor,oos_drawdown_pct\n")
MODES = ("long", "short", "long_short")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    from src.research.timeframes import TIMEFRAMES, load_research_bars, sample_period, source_path
    from src.research.manifest import update_manifest
    p.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=TIMEFRAMES)
    p.add_argument("--symbols", nargs="*", help="optional subset for validation")
    p.add_argument("--limit", type=int, default=0, help="optional validation limit")
    p.add_argument("--max-period", type=int, default=200)
    p.add_argument("--train-start", default="2022-01-01")
    p.add_argument("--oos-start", default="2025-01-01")
    p.add_argument("--fee-bps", type=float, default=5)
    p.add_argument("--slip-bps", type=float, default=0)
    p.add_argument("--out", type=Path, default=EXPERIMENT / "results")
    args = p.parse_args()
    if args.max_period < 3:
        p.error("--max-period must be >= 3")
    args.out.mkdir(parents=True, exist_ok=True)
    executable = args.out / "ema_grid_kernel"
    subprocess.run(["g++", "-std=c++17", "-O3", str(EXPERIMENT / "kernel.cpp"), "-o", str(executable)], check=True)
    universe = json.loads(UNIVERSE.read_text())
    equities = [x for x in universe if x.get("SECTYPE") in ("1", "2")]
    if args.symbols:
        wanted = set(args.symbols)
        equities = [x for x in equities if x["SECID"] in wanted]
    if args.limit:
        equities = equities[:args.limit]
    snapshot = {"universe_source": str(UNIVERSE.relative_to(ROOT)),
                "universe_snapshot": "2026-10-30", "equity_types": ["1", "2"],
                "eligible_equities": len(equities), "cached_daily": 0, "cached_hourly": 0,
                "max_period": args.max_period, "pairs": (args.max_period - 1) * (args.max_period - 2) // 2,
                "modes": list(MODES), "timeframes": args.timeframes,
                "train_start": args.train_start, "oos_start": args.oos_start,
                "minute_sample_period": sample_period("15M"),
                "fee_bps": args.fee_bps, "slip_bps": args.slip_bps,
                "fill": "signal on confirmed close; fill next bar open plus one tick; size rounded to integer shares"}
    update_manifest(args.out / "manifest.json", snapshot, protocol_keys=(
        "universe_source", "universe_snapshot", "equity_types", "max_period",
        "pairs", "modes", "train_start", "oos_start", "fee_bps", "slip_bps", "fill"))
    progress = args.out / "progress.csv"
    if not progress.exists():
        progress.write_text("symbol,timeframe,status,bars,seconds,detail\n")
    jobs = [(x, tf) for x in equities for tf in args.timeframes]
    for index, (security, tf) in enumerate(jobs, 1):
        symbol = security["SECID"]
        source = source_path(CACHE, symbol, tf)
        target = args.out / tf / f"{symbol}.csv.gz"
        target.parent.mkdir(parents=True, exist_ok=True)
        status, detail, bar_count = "", "", 0
        began = time.monotonic()
        if target.exists():
            status = "complete_previous"
        elif not source.exists():
            status, detail = "missing_cache", str(source.relative_to(ROOT))
        else:
            try:
                bars = load_research_bars(CACHE, symbol, tf)
                bar_count = len(bars)
                if bar_count < 5:
                    status = "insufficient_bars"
                else:
                    with tempfile.TemporaryFile(mode="w+t") as input_file:
                        for bar in bars:
                            input_file.write(f'{bar["ts"]},{bar["open"]},{bar["close"]}\n')
                        input_file.seek(0)
                        train_start, oos_start = sample_period(tf) if tf in ("15M", "30M") else (args.train_start, args.oos_start)
                        proc = subprocess.Popen([str(executable), train_start, oos_start,
                                                 str(args.fee_bps), str(args.slip_bps),
                                                 str(security.get("MINSTEP") or 0),
                                                 str(args.max_period)], stdin=input_file,
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                text=True)
                        temp = target.with_suffix(".tmp")
                        with gzip.open(temp, "wt", encoding="utf-8", newline="") as output:
                            output.write(HEADER)
                            for line in proc.stdout:
                                parts = line.rstrip().split(",")
                                if len(parts) != 16:
                                    raise ValueError(f"bad kernel row: {line[:100]}")
                                parts[2] = MODES[int(parts[2])]
                                output.write(f"{symbol},{tf}," + ",".join(parts) + "\n")
                        stderr = proc.stderr.read()
                        if proc.wait():
                            raise RuntimeError(stderr)
                        temp.replace(target)
                    status = "complete"
            except Exception as exc:
                status, detail = "error", str(exc).replace(",", ";")[:300]
                target.with_suffix(".tmp").unlink(missing_ok=True)
        elapsed = round(time.monotonic() - began, 2)
        with progress.open("a", newline="") as file:
            csv.writer(file).writerow([symbol, tf, status, bar_count, elapsed, detail])
        print(f"[{index}/{len(jobs)}] {symbol} {tf}: {status} bars={bar_count} {elapsed}s", flush=True)
    print(f"Completed cached sweep. See {progress}", flush=True)


if __name__ == "__main__":
    main()
