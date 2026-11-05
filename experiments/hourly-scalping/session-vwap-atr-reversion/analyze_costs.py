"""Full-universe cost stress for the diagnostic least-bad VWAP variant."""

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.research_ema_combinations import simulate
from src.research.annual_returns import calendar_years
from src.research.hourly_scalping_signals import signals
from src.research.monthly_efficiency import continuous_monthly_windows
from src.research.timeframes import load_research_bars, source_path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
CACHE = ROOT / "data/candles/moex_scan"
VARIANT = "vwap_1.5_4"


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    universe = json.loads((ROOT / protocol["eligible_universe"]["snapshot_file"]).read_text())
    symbols = sorted({item["SECID"] for item in universe if item["BOARDID"] == "TQBR"
                      and source_path(CACHE, item["SECID"], "1H").exists()})
    output = []
    for symbol in symbols:
        bars = load_research_bars(CACHE, symbol, "1H")
        if len(bars) < protocol["min_bars"]:
            continue
        entries, exits = signals(bars, 1.5, 4)
        observed = {bar["ts"][:7] for bar in bars if bar["ts"] >= protocol["start"]}
        for fee in (0, 15, 30):
            curve, trades = [], []
            simulate(bars, entries, [True] * len(bars), [True] * len(bars),
                     0.0, protocol["start"], fee_bps=fee,
                     equity_curve=curve, trade_log=trades, exit_signals=exits)
            monthly = [item for item in continuous_monthly_windows(
                bars, curve, trades, 2024, protocol["split"])["all"]
                if item["start"][:7] in observed]
            for year in calendar_years(monthly):
                output.append({"symbol": symbol, "variant": VARIANT,
                               "fee_bps_per_side": fee, **year})
    with (OUT / "cost_stress_yearly.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    for fee in (0, 15, 30):
        rows = [row for row in output if row["fee_bps_per_side"] == fee]
        for year in sorted({row["year"] for row in rows}):
            sample = [row["return_pct"] for row in rows
                      if row["year"] == year and
                      (row["complete"] or (year == "2026" and row["months"] == 9))
                      and row["first_month"] == 1]
            if sample:
                print(f"{fee} bps/side {year} n={len(sample)} median={statistics.median(sample):+.2f}%", flush=True)


if __name__ == "__main__":
    main()
