"""Explore whether range age and channel geometry forecast the next breakout.

This is an event study, not a trade signal. Repeated observations from one
range episode and overlapping future windows must not be treated as independent.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.research.market_regime import CACHE, EXPERIMENT, ROOT, classify, write_csv
from src.research.standalone_grid import atr
from src.research.timeframes import TIMEFRAMES, load_research_bars, sample_period

PROTOCOL = EXPERIMENT / "transition_protocol.json"
EVENT_FIELDS = ("symbol", "timeframe", "ts", "sample", "horizon", "episode_start",
                "age_bars", "age_days", "duration_bin", "channel_position",
                "channel_slope_atr_per_bar", "slope_bin", "weekday", "outcome")
SUMMARY_FIELDS = ("symbol", "timeframe", "sample", "horizon", "feature", "bucket",
                  "observations", "episode_count", "up_pct", "down_pct", "no_break_pct",
                  "baseline_group", "baseline_up_pct", "baseline_down_pct", "baseline_no_break_pct")


def first_breakout(bars: list[dict], index: int, horizon: int,
                   support: float, resistance: float) -> str:
    """First future *close* outside boundaries fixed at index."""
    for future in bars[index + 1:index + horizon + 1]:
        if future["close"] > resistance:
            return "up"
        if future["close"] < support:
            return "down"
    return "no_break"


def channel_slope_atr(bars: list[dict], index: int, lookback: int,
                      volatility: float) -> float:
    """Least-squares slope from bars before index, in ATR per bar."""
    if index < lookback or not math.isfinite(volatility) or volatility <= 0:
        return math.nan
    closes = [bar["close"] for bar in bars[index - lookback:index]]
    center = (lookback - 1) / 2
    denominator = sum((j - center) ** 2 for j in range(lookback))
    return sum((j - center) * value for j, value in enumerate(closes)) / denominator / volatility


def events_for_series(bars: list[dict], symbol: str, timeframe: str, protocol: dict) -> list[dict]:
    lookback = protocol["lookback_bars"]
    labels = classify(bars, lookback, protocol["max_range_width_atr"],
                      protocol["min_trend_displacement_atr"])
    volatility = atr(bars, 14)
    split = sample_period(timeframe)[1]
    events = []
    episode_start = None
    frozen_support = frozen_resistance = math.nan
    for i, (bar, state) in enumerate(zip(bars, labels)):
        ended = False
        if (episode_start is not None and
                not frozen_support <= bar["close"] <= frozen_resistance):
            episode_start = None
            ended = True
        if episode_start is None:
            # Do not start a new zone on the same candle that broke an old one.
            if ended or state["label"] != "range":
                continue
            episode_start = i
            frozen_support, frozen_resistance = state["support"], state["resistance"]
        support, resistance = frozen_support, frozen_resistance
        if resistance <= support:
            continue
        age_days = (date.fromisoformat(bar["ts"][:10]) -
                    date.fromisoformat(bars[episode_start]["ts"][:10])).days
        duration_bin = "0-1d" if age_days <= 1 else "2-5d" if age_days <= 5 else "6+d"
        position = (bar["close"] - support) / (resistance - support)
        channel_position = "lower" if position < 1 / 3 else "middle" if position < 2 / 3 else "upper"
        slope = channel_slope_atr(bars, i, lookback, volatility[i])
        threshold = protocol["slope_bins_atr_per_bar"][1]
        slope_bin = "up" if slope > threshold else "down" if slope < -threshold else "flat"
        for horizon in protocol["forward_horizons_bars"]:
            if i + horizon >= len(bars):
                continue
            sample = ("train" if bars[i + horizon]["ts"][:10] < split else
                      "holdout" if bar["ts"][:10] >= split else None)
            if sample is None:
                continue
            events.append({"symbol": symbol, "timeframe": timeframe, "ts": bar["ts"],
                           "sample": sample, "horizon": horizon,
                           "episode_start": bars[episode_start]["ts"],
                           "age_bars": i - episode_start + 1, "age_days": age_days,
                           "duration_bin": duration_bin, "channel_position": channel_position,
                           "channel_slope_atr_per_bar": round(slope, 5), "slope_bin": slope_bin,
                           "weekday": date.fromisoformat(bar["ts"][:10]).weekday(),
                           "outcome": first_breakout(bars, i, horizon, support, resistance)})
    return events


def summarize_events(events: list[dict]) -> list[dict]:
    baseline: dict[tuple[str, str, int, str], list[dict]] = defaultdict(list)
    groups: dict[tuple[str, str, int, str, str, object], list[dict]] = defaultdict(list)
    for row in events:
        key = (row["symbol"], row["timeframe"], row["horizon"])
        sample = row["sample"]
        baseline[(key[0], key[1], key[2], sample)].append(row)
        for feature in ("duration_bin", "channel_position", "slope_bin", "weekday"):
            groups[(key[0], key[1], key[2], sample, feature, row[feature])].append(row)
        for feature, value in (("duration_within_position", row["duration_bin"]),
                               ("slope_within_position", row["slope_bin"]),
                               ("weekday_within_position", row["weekday"])):
            bucket = f'{row["channel_position"]}|{value}'
            groups[(key[0], key[1], key[2], sample, feature, bucket)].append(row)
    for (symbol, timeframe, horizon, sample), rows in baseline.items():
        groups[(symbol, timeframe, horizon, sample, "all", "all")] = rows
    output = []
    for (symbol, timeframe, horizon, sample, feature, bucket), rows in sorted(groups.items()):
        baseline_group = ("same_channel_position" if feature.endswith("_within_position")
                          else "all_range_events")
        common = baseline[(symbol, timeframe, horizon, sample)]
        if baseline_group == "same_channel_position":
            position = bucket.split("|", 1)[0]
            common = [row for row in common if row["channel_position"] == position]
        rate = lambda data, outcome: round(100 * sum(row["outcome"] == outcome for row in data) / len(data), 2)
        output.append({"symbol": symbol, "timeframe": timeframe, "sample": sample,
                       "horizon": horizon, "feature": feature, "bucket": bucket,
                       "observations": len(rows),
                       "episode_count": len({row["episode_start"] for row in rows}),
                       "up_pct": rate(rows, "up"), "down_pct": rate(rows, "down"),
                       "no_break_pct": rate(rows, "no_break"),
                       "baseline_group": baseline_group,
                       "baseline_up_pct": rate(common, "up"),
                       "baseline_down_pct": rate(common, "down"),
                       "baseline_no_break_pct": rate(common, "no_break")})
    return output


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=TIMEFRAMES)
    parser.add_argument("--out", type=Path, default=EXPERIMENT / "transition-results")
    parser.add_argument("--store-events", action="store_true",
                        help="also retain every overlapping event; can use substantial disk space")
    args = parser.parse_args(argv)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe = [item for item in json.loads((ROOT / "data/moex_scan/universe_2026-10-30.json").read_text())
                if item.get("SECTYPE") in ("1", "2")]
    if args.symbols:
        wanted = set(args.symbols)
        universe = [item for item in universe if item["SECID"] in wanted]
    args.out.mkdir(parents=True, exist_ok=True)
    progress_path = args.out / "progress.csv"
    write_csv(progress_path, ("symbol", "timeframe", "status", "events", "detail"), [])
    for item in universe:
        symbol = item["SECID"]
        for timeframe in args.timeframes:
            try:
                bars = load_research_bars(CACHE, symbol, timeframe)
                if len(bars) < 250:
                    raise ValueError(f"insufficient_bars:{len(bars)}")
                events = events_for_series(bars, symbol, timeframe, protocol)
                target = args.out / timeframe / symbol
                if args.store_events:
                    write_csv(target / "events.csv", EVENT_FIELDS, events)
                write_csv(target / "summary.csv", SUMMARY_FIELDS, summarize_events(events))
                status, detail = "complete", ""
            except (OSError, ValueError, KeyError, TypeError) as exc:
                status, detail, events = "skipped", str(exc), []
            with progress_path.open("a", newline="", encoding="utf-8") as stream:
                csv.DictWriter(stream, fieldnames=("symbol", "timeframe", "status", "events", "detail")).writerow(
                    {"symbol": symbol, "timeframe": timeframe, "status": status,
                     "events": len(events), "detail": detail.replace(",", ";")})
            print(f"{symbol} {timeframe}: {status} events={len(events)} {detail}", flush=True)


if __name__ == "__main__":
    run()
