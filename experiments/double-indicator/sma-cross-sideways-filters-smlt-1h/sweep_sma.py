"""Exhaust all fast<slow SMA pairs in 2..200 on the fixed SMLT 1H snapshot.

The sweep is exploratory. It writes one row per pair and rule, resumes safely,
and never changes a strategy or paper trading account.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate
from src.research.indicator_library import crosses, sma
from src.research.standalone_grid import atr, load_bars

from run import hysteresis_signals

HERE = Path(__file__).resolve().parent
OUT = HERE / "results/sma_2_200_sweep.csv"
PROGRESS = HERE / "results/sma_2_200_progress.json"
FIELDS = ("fast", "slow", "rule", "return_pct", "closed_trades", "winning_trades",
          "profit_factor", "max_drawdown_pct")
RULES = ("cross", "atr14_hysteresis_0.25")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bars = load_bars("SMLT", "1H")
    close = [bar["close"] for bar in bars]
    moving = {period: sma(close, period) for period in range(2, 201)}
    volatility = atr(bars, 14)
    allowed = [True] * len(bars)
    done = set()
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as stream:
            done = {(int(row["fast"]), int(row["slow"]), row["rule"])
                    for row in csv.DictReader(stream)}
    started = time.monotonic()
    with OUT.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if not done:
            writer.writeheader()
        for fast in range(2, 200):
            for slow in range(fast + 1, 201):
                pending = [rule for rule in RULES if (fast, slow, rule) not in done]
                if not pending:
                    continue
                for rule in pending:
                    signals = (crosses(moving[fast], moving[slow]) if rule == "cross" else
                               hysteresis_signals(moving[fast], moving[slow], volatility, 0.25))
                    result = simulate(bars, signals, allowed, allowed, 0.2, "2024-01-01")
                    writer.writerow({"fast": fast, "slow": slow, "rule": rule,
                                     "return_pct": result["return_pct"],
                                     "closed_trades": result["closed_trades"],
                                     "winning_trades": result["winning_trades"],
                                     "profit_factor": result["profit_factor"],
                                     "max_drawdown_pct": result["max_drawdown_pct"]})
                    done.add((fast, slow, rule))
            stream.flush()
            PROGRESS.write_text(json.dumps({"completed_rows": len(done),
                                            "total_rows": 2 * 19701,
                                            "last_fast": fast,
                                            "elapsed_seconds": round(time.monotonic() - started, 1)},
                                           indent=2) + "\n", encoding="utf-8")
            if fast % 10 == 0:
                print(f"fast={fast} rows={len(done)}/39402", flush=True)
    print(f"complete rows={len(done)} elapsed={time.monotonic() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
