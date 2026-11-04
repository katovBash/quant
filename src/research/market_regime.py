"""Causal forecasts of ranges, rising prices, and falling prices.

Protocol: experiments/market-regime-grid-search/protocol.json.
Results are exploratory; a selected maximum is not evidence of an edge.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from src.research.standalone_grid import atr
from src.research.timeframes import TIMEFRAMES, load_research_bars, sample_period

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = ROOT / "experiments/market-regime-grid-search"
CACHE = ROOT / "data/moex_scan"
PROTOCOL = EXPERIMENT / "protocol.json"
FORECAST_FIELDS = ("symbol", "timeframe", "lookback", "max_width_atr", "min_displacement_atr",
                   "horizon", "sample", "label", "observations", "outcome",
                   "hit_rate_pct", "baseline_hit_rate_pct", "baseline_type", "lift_pp",
                   "mean_forward_return_pct")
STABILITY_FIELDS = ("symbol", "timeframe", "sample", "comparison", "lookback",
                    "setting_a", "setting_b", "label", "value_pct", "observations")


def classify(bars: list[dict], lookback: int, max_width_atr: float,
             min_displacement_atr: float) -> list[dict]:
    """Use only completed bars through i; range boundaries use bars before i."""
    volatility = atr(bars, 14)
    result = []
    for i, bar in enumerate(bars):
        item = {"label": "uncertain", "support": math.nan, "resistance": math.nan}
        if i >= lookback and math.isfinite(volatility[i]) and volatility[i] > 0:
            previous = bars[i - lookback:i]
            support = min(x["low"] for x in previous)
            resistance = max(x["high"] for x in previous)
            displacement = (bar["close"] - bars[i - lookback]["close"]) / volatility[i]
            width = (resistance - support) / volatility[i]
            if (width <= max_width_atr and abs(displacement) < min_displacement_atr
                    and support <= bar["close"] <= resistance):
                label = "range"
            elif displacement >= min_displacement_atr and bar["close"] > resistance:
                label = "trend_up"
            elif displacement <= -min_displacement_atr and bar["close"] < support:
                label = "trend_down"
            else:
                label = "uncertain"
            item = {"label": label, "support": support, "resistance": resistance}
        result.append(item)
    return result


def forecast(bars: list[dict], labels: list[dict], horizon: int, split: str,
             symbol: str, timeframe: str, config: dict) -> list[dict]:
    """Hit rates against a simple outcome baseline on the same ticker and sample.

    A range hit means every one of the next H closes stays in the boundaries
    frozen at the prediction time. Trend hits use the H-th close direction.
    Windows can overlap, so these rates are descriptive, not independent trials.
    """
    grouped: dict[tuple[str, str], list[tuple[float, dict[str, bool]]]] = {}
    baseline: dict[str, list[tuple[dict[str, bool], bool]]] = {"train": [], "holdout": []}
    for i in range(len(bars) - horizon):
        if not math.isfinite(labels[i]["support"]):
            continue
        # Only outcomes fully contained in one side of the split are counted.
        sample = "train" if bars[i + horizon]["ts"][:10] < split else "holdout" if bars[i]["ts"][:10] >= split else None
        if sample is None:
            continue
        forward = 100 * (bars[i + horizon]["close"] / bars[i]["close"] - 1)
        outcomes = {
            "range": all(labels[i]["support"] <= bars[j]["close"] <= labels[i]["resistance"]
                         for j in range(i + 1, i + horizon + 1)),
            "trend_up": forward > 0,
            "trend_down": forward < 0,
        }
        grouped.setdefault((sample, labels[i]["label"]), []).append((forward, outcomes))
        inside_now = labels[i]["support"] <= bars[i]["close"] <= labels[i]["resistance"]
        baseline[sample].append((outcomes, inside_now))
    rows = []
    for sample in ("train", "holdout"):
        for label in ("range", "trend_up", "trend_down", "uncertain"):
            values = grouped.get((sample, label), [])
            predicted = label if label != "uncertain" else None
            rate = (100 * sum(outcomes[predicted] for _, outcomes in values) / len(values)
                    if predicted and values else None)
            reference = [(outcomes, inside_now) for outcomes, inside_now in baseline[sample]
                         if label != "range" or inside_now]
            baseline_rate = (100 * sum(outcomes[predicted] for outcomes, _ in reference) / len(reference)
                             if predicted and reference else None)
            rows.append({"symbol": symbol, "timeframe": timeframe, **config, "horizon": horizon,
                         "sample": sample, "label": label, "observations": len(values),
                         "outcome": ("all_next_closes_inside_frozen_range" if label == "range" else
                                     "last_close_higher" if label == "trend_up" else
                                     "last_close_lower" if label == "trend_down" else "no_forecast"),
                         "hit_rate_pct": round(rate, 2) if rate is not None else "",
                         "baseline_hit_rate_pct": round(baseline_rate, 2) if baseline_rate is not None else "",
                         "baseline_type": ("current_close_inside_prior_range" if label == "range" else
                                           "all_valid_bars" if predicted else "none"),
                         "lift_pp": round(rate - baseline_rate, 2) if rate is not None and baseline_rate is not None else "",
                         "mean_forward_return_pct": round(sum(x[0] for x in values) / len(values), 4) if values else ""})
    return rows


def stability(bars: list[dict], by_config: dict[tuple[int, float, float], list[dict]],
              split: str, symbol: str, timeframe: str) -> list[dict]:
    """Adjacent-threshold agreement and train/holdout label-frequency drift."""
    rows = []
    configs = sorted(by_config)
    for a in configs:
        for b in configs:
            if b <= a or a[0] != b[0]:
                continue
            adjacent = ((a[1] != b[1] and a[2] == b[2]) or
                        (a[1] == b[1] and a[2] != b[2]))
            if not adjacent:
                continue
            for sample in ("train", "holdout"):
                indices = [i for i, bar in enumerate(bars) if i >= a[0] and
                           (bar["ts"][:10] < split) == (sample == "train")]
                if not indices:
                    continue
                matches = sum(by_config[a][i]["label"] == by_config[b][i]["label"] for i in indices)
                rows.append({"symbol": symbol, "timeframe": timeframe, "sample": sample,
                             "comparison": "neighbor_agreement", "lookback": a[0],
                             "setting_a": str(a), "setting_b": str(b), "label": "all",
                             "value_pct": round(100 * matches / len(indices), 2),
                             "observations": len(indices)})
    for config in configs:
        train = [x["label"] for i, x in enumerate(by_config[config]) if
                 i >= config[0] and bars[i]["ts"][:10] < split]
        holdout = [x["label"] for i, x in enumerate(by_config[config]) if
                   i >= config[0] and bars[i]["ts"][:10] >= split]
        if not train or not holdout:
            continue
        for label in ("range", "trend_up", "trend_down", "uncertain"):
            drift = 100 * (holdout.count(label) / len(holdout) - train.count(label) / len(train))
            rows.append({"symbol": symbol, "timeframe": timeframe, "sample": "holdout_vs_train",
                         "comparison": "label_frequency_change_pp", "lookback": config[0],
                         "setting_a": str(config), "setting_b": "", "label": label,
                         "value_pct": round(drift, 2),
                         "observations": len(train) + len(holdout)})
    return rows


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=TIMEFRAMES)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path, default=EXPERIMENT / "results")
    args = parser.parse_args(argv)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe = [x for x in json.loads((ROOT / protocol["snapshot_universe"]).read_text(encoding="utf-8"))
                if x.get("SECTYPE") in ("1", "2")]
    if args.symbols:
        universe = [x for x in universe if x["SECID"] in set(args.symbols)]
    if args.limit:
        universe = universe[:args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(json.dumps({"protocol": str(PROTOCOL.relative_to(ROOT)),
        "symbols": [x["SECID"] for x in universe], "timeframes": args.timeframes,
        "holdout_by_timeframe": {tf: sample_period(tf)[1] for tf in args.timeframes},
        "study": "forecast_only", "protocol_version": 2,
        "note": "Overlapping prediction windows; late dates were explored previously and are not a blind test."},
        ensure_ascii=False, indent=2), encoding="utf-8")
    progress_path = args.out / "progress.csv"
    with progress_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("symbol", "timeframe", "status", "detail"))
        writer.writeheader()
    for item in universe:
        symbol = item["SECID"]
        for timeframe in args.timeframes:
            target = args.out / timeframe / symbol
            if (target / "forecast.csv").exists() and (target / "stability.csv").exists():
                status, detail = "complete_previous", "existing forecast and stability CSV"
            else:
                try:
                    bars = load_research_bars(CACHE, symbol, timeframe)
                    if len(bars) < 250:
                        raise ValueError(f"insufficient_bars:{len(bars)}")
                    split = sample_period(timeframe)[1]
                    forecasts = []
                    by_config = {}
                    for lookback in protocol["grid"]["lookback_bars"]:
                        for width in protocol["grid"]["max_range_width_atr"]:
                            for displacement in protocol["grid"]["min_trend_displacement_atr"]:
                                config = {"lookback": lookback, "max_width_atr": width,
                                          "min_displacement_atr": displacement}
                                labels = classify(bars, lookback, width, displacement)
                                by_config[(lookback, width, displacement)] = labels
                                for horizon in protocol["grid"]["forward_horizon_bars"]:
                                    forecasts.extend(forecast(bars, labels, horizon, split, symbol, timeframe, config))
                    write_csv(target / "forecast.csv", FORECAST_FIELDS, forecasts)
                    checks = stability(bars, by_config, split, symbol, timeframe)
                    write_csv(target / "stability.csv", STABILITY_FIELDS, checks)
                    (target / "stage1.csv").unlink(missing_ok=True)
                    (target / "stage2.csv").unlink(missing_ok=True)
                    status, detail = "complete", f"forecasts={len(forecasts)} stability={len(checks)}"
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    status, detail = "skipped", str(exc)
            with progress_path.open("a", newline="", encoding="utf-8") as stream:
                csv.DictWriter(stream, fieldnames=("symbol", "timeframe", "status", "detail")).writerow(
                    {"symbol": symbol, "timeframe": timeframe, "status": status,
                     "detail": detail.replace(",", ";")})
            print(f"{symbol} {timeframe}: {status} {detail}", flush=True)


if __name__ == "__main__":
    run()
