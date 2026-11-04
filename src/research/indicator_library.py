"""One hundred preregistered indicator rules over cached MOEX candles.

Each rule is a distinct fixed signal hypothesis. All use the same next-open
backtest and long+short mode. The full search is exploratory, not a holdout.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from src.ema.core.research_ema_combinations import simulate
from src.research.standalone_grid import CACHE, ROOT, UNIVERSE, buy_hold_return, load_bars
from src.research.timeframes import TIMEFRAMES, sample_period
from src.research.manifest import update_manifest

FAMILIES = ("sma_cross", "bollinger_reversal", "bollinger_breakout",
            "donchian_breakout", "donchian_reversal", "macd_cross", "macd_zero",
            "roc_momentum", "cci_reversal", "williams_reversal")
INDICATORS = {
    "sma": ("sma_cross",),
    "bollinger": ("bollinger_reversal", "bollinger_breakout"),
    "donchian": ("donchian_breakout", "donchian_reversal"),
    "macd": ("macd_cross", "macd_zero"),
    "roc": ("roc_momentum",),
    "cci": ("cci_reversal",),
    "williams-r": ("williams_reversal",),
}
FIELDS = ("symbol", "timeframe", "rule_id", "family", "parameters", "bars", "first_bar",
          "last_bar", "closed_trades", "winning_trades", "win_rate_pct", "net_return_pct",
          "buy_hold_return_pct", "excess_vs_hold_pp", "profit_factor", "max_drawdown_pct",
          "late_trades", "late_wins", "late_return_pct", "late_profit_factor", "late_drawdown_pct")


def specifications() -> list[dict]:
    params = {
        "sma_cross": [{"fast": fast, "slow": slow} for fast, slow in
                      ((3, 15), (5, 20), (6, 33), (9, 30), (10, 50), (12, 60),
                       (20, 100), (30, 120), (50, 150), (66, 200))],
        "bollinger_reversal": [{"period": period, "sigma": sigma}
                               for period in (10, 20, 30, 40, 50) for sigma in (1.5, 2.0)],
        "bollinger_breakout": [{"period": period, "sigma": sigma}
                               for period in (10, 20, 30, 40, 50) for sigma in (1.5, 2.0)],
        "donchian_breakout": [{"period": period} for period in (5, 10, 15, 20, 30, 40, 50, 66, 100, 150)],
        "donchian_reversal": [{"period": period} for period in (5, 10, 15, 20, 30, 40, 50, 66, 100, 150)],
        "macd_cross": [{"fast": fast, "slow": slow, "signal": signal} for fast, slow, signal in
                       ((5, 13, 5), (6, 19, 6), (8, 21, 7), (9, 26, 9), (12, 26, 9),
                        (12, 33, 9), (13, 48, 9), (20, 50, 10), (21, 66, 12), (30, 100, 15))],
        "macd_zero": [{"fast": fast, "slow": slow, "signal": signal} for fast, slow, signal in
                      ((5, 13, 5), (6, 19, 6), (8, 21, 7), (9, 26, 9), (12, 26, 9),
                       (12, 33, 9), (13, 48, 9), (20, 50, 10), (21, 66, 12), (30, 100, 15))],
        "roc_momentum": [{"period": period, "threshold_pct": threshold}
                         for period in (3, 5, 10, 20, 40) for threshold in (1, 3)],
        "cci_reversal": [{"period": period, "threshold": threshold}
                         for period in (10, 14, 20, 30, 40) for threshold in (100, 150)],
        "williams_reversal": [{"period": period, "lower": lower, "upper": upper}
                              for period in (7, 10, 14, 21, 30) for lower, upper in ((-80, -20), (-90, -10))],
    }
    specs = []
    for family, configurations in params.items():
        for number, values in enumerate(configurations, 1):
            specs.append({"rule_id": f"{family}-{number:02d}", "family": family, "parameters": values})
    assert len(specs) == 100 and len({spec["rule_id"] for spec in specs}) == 100
    return specs


def ema(values: list[float], period: int) -> list[float]:
    alpha = 2 / (period + 1)
    output = []
    for value in values:
        output.append(value if not output else alpha * value + (1 - alpha) * output[-1])
    return output


def sma(values: list[float], period: int) -> list[float]:
    output = [math.nan] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= period:
            total -= values[index - period]
        if index + 1 >= period:
            output[index] = total / period
    return output


def crosses(upper: list[float], lower: list[float]) -> list[int]:
    output = [0] * len(upper)
    for index in range(1, len(upper)):
        if all(math.isfinite(value) for value in
               (upper[index], lower[index], upper[index - 1], lower[index - 1])):
            if upper[index - 1] <= lower[index - 1] and upper[index] > lower[index]:
                output[index] = 1
            elif upper[index - 1] >= lower[index - 1] and upper[index] < lower[index]:
                output[index] = -1
    return output


def edges(up: list[bool], down: list[bool]) -> list[int]:
    return [1 if up[i] and (i == 0 or not up[i - 1]) and not down[i]
            else -1 if down[i] and (i == 0 or not down[i - 1]) and not up[i]
            else 0 for i in range(len(up))]


def signal_series(bars: list[dict], spec: dict) -> list[int]:
    family, p = spec["family"], spec["parameters"]
    close = [bar["close"] for bar in bars]
    n = len(bars)
    if family == "sma_cross":
        return crosses(sma(close, p["fast"]), sma(close, p["slow"]))
    if family.startswith("bollinger"):
        period, sigma = p["period"], p["sigma"]
        means = sma(close, period)
        upper, lower = [math.nan] * n, [math.nan] * n
        for i in range(period - 1, n):
            deviation = math.sqrt(sum((value - means[i]) ** 2 for value in close[i - period + 1:i + 1]) / period)
            upper[i], lower[i] = means[i] + sigma * deviation, means[i] - sigma * deviation
        if family == "bollinger_breakout":
            up = [math.isfinite(upper[i]) and close[i] > upper[i] for i in range(n)]
            down = [math.isfinite(lower[i]) and close[i] < lower[i] for i in range(n)]
            return edges(up, down)
        result = [0] * n
        for i in range(1, n):
            if (math.isfinite(lower[i - 1]) and math.isfinite(lower[i]) and
                    close[i - 1] < lower[i - 1] and close[i] >= lower[i]):
                result[i] = 1
            elif (math.isfinite(upper[i - 1]) and math.isfinite(upper[i]) and
                    close[i - 1] > upper[i - 1] and close[i] <= upper[i]):
                result[i] = -1
        return result
    if family.startswith("donchian"):
        period = p["period"]
        up, down = [False] * n, [False] * n
        for i in range(period, n):
            upper = max(bar["high"] for bar in bars[i - period:i])
            lower = min(bar["low"] for bar in bars[i - period:i])
            if family == "donchian_breakout":
                up[i], down[i] = close[i] > upper, close[i] < lower
            else:
                up[i] = bars[i]["low"] < lower and close[i] > lower
                down[i] = bars[i]["high"] > upper and close[i] < upper
        return edges(up, down)
    if family.startswith("macd"):
        fast, slow = ema(close, p["fast"]), ema(close, p["slow"])
        macd = [a - b for a, b in zip(fast, slow)]
        comparison = ema(macd, p["signal"]) if family == "macd_cross" else [0.0] * n
        return crosses(macd, comparison)
    if family == "roc_momentum":
        period, threshold = p["period"], p["threshold_pct"]
        roc = [math.nan] * n
        for i in range(period, n):
            if close[i - period] > 0:
                roc[i] = 100 * (close[i] / close[i - period] - 1)
        return crosses(roc, [threshold] * n) if threshold == 0 else [
            1 if i and math.isfinite(roc[i - 1]) and roc[i - 1] <= threshold < roc[i]
            else -1 if i and math.isfinite(roc[i - 1]) and roc[i - 1] >= -threshold > roc[i]
            else 0 for i in range(n)]
    if family == "cci_reversal":
        period, threshold = p["period"], p["threshold"]
        typical = [(bar["high"] + bar["low"] + bar["close"]) / 3 for bar in bars]
        means = sma(typical, period)
        cci = [math.nan] * n
        for i in range(period - 1, n):
            deviation = sum(abs(value - means[i]) for value in typical[i - period + 1:i + 1]) / period
            cci[i] = (typical[i] - means[i]) / (0.015 * deviation) if deviation else 0.0
        return [1 if i and cci[i - 1] <= -threshold < cci[i]
                else -1 if i and cci[i - 1] >= threshold > cci[i]
                else 0 for i in range(n)]
    if family == "williams_reversal":
        period, low, high = p["period"], p["lower"], p["upper"]
        values = [math.nan] * n
        for i in range(period - 1, n):
            highest = max(bar["high"] for bar in bars[i - period + 1:i + 1])
            lowest = min(bar["low"] for bar in bars[i - period + 1:i + 1])
            values[i] = -100 * (highest - close[i]) / (highest - lowest) if highest > lowest else -50.0
        return [1 if i and values[i - 1] <= low < values[i]
                else -1 if i and values[i - 1] >= high > values[i]
                else 0 for i in range(n)]
    raise ValueError(family)


def evaluate(symbol: str, timeframe: str, bars: list[dict], tick: float, specs: list[dict]) -> list[dict]:
    start, late_start = sample_period(timeframe)
    always = [True] * len(bars)
    hold = buy_hold_return(bars, start, tick)
    rows = []
    for spec in specs:
        signals = signal_series(bars, spec)
        whole = simulate(bars, signals, always, always, tick, start)
        late = simulate(bars, signals, always, always, tick, late_start)
        trades = whole["closed_trades"]
        rows.append({"symbol": symbol, "timeframe": timeframe, "rule_id": spec["rule_id"],
                     "family": spec["family"], "parameters": json.dumps(spec["parameters"], sort_keys=True),
                     "bars": len(bars), "first_bar": bars[0]["ts"], "last_bar": bars[-1]["ts"],
                     "closed_trades": trades, "winning_trades": whole["winning_trades"],
                     "win_rate_pct": round(100 * whole["winning_trades"] / trades, 2) if trades else "",
                     "net_return_pct": whole["return_pct"], "buy_hold_return_pct": hold,
                     "excess_vs_hold_pp": round(whole["return_pct"] - hold, 2),
                     "profit_factor": whole["profit_factor"], "max_drawdown_pct": whole["max_drawdown_pct"],
                     "late_trades": late["closed_trades"], "late_wins": late["winning_trades"],
                     "late_return_pct": late["return_pct"], "late_profit_factor": late["profit_factor"],
                     "late_drawdown_pct": late["max_drawdown_pct"]})
    return rows


def run(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--indicator", choices=tuple(INDICATORS),
                        help="one indicator experiment to run")
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=TIMEFRAMES)
    parser.add_argument("--out", type=Path,
                        help="output directory; required for a combined research batch")
    args = parser.parse_args(argv)
    specs = specifications()
    if args.indicator:
        specs = [spec for spec in specs if spec["family"] in INDICATORS[args.indicator]]
        args.out = args.out or ROOT / "experiments" / f"{args.indicator}-grid-search" / "results"
    elif args.out is None:
        parser.error("choose --indicator for a separate experiment or provide --out for a batch")
    args.out.mkdir(parents=True, exist_ok=True)
    universe = [item for item in json.loads(UNIVERSE.read_text()) if item.get("SECTYPE") in ("1", "2")]
    if args.symbols:
        wanted = set(args.symbols)
        universe = [item for item in universe if item["SECID"] in wanted]
    update_manifest(args.out / "manifest.json", {"rules": specs, "universe": str(UNIVERSE.relative_to(ROOT)),
        "symbols": [item["SECID"] for item in universe], "timeframes": args.timeframes,
        "fill": "closed-bar signal; next-open fill; 25% equity; one-tick slip; 5 bps fee per side",
        "mode": "long_short", "short_costs_complete": False, "late_period_independent": False,
        "late_start_by_timeframe": {tf: sample_period(tf)[1] for tf in args.timeframes}},
        protocol_keys=("rules", "universe", "fill", "mode", "short_costs_complete"))
    progress = args.out / "progress.csv"
    if not progress.exists():
        progress.write_text("symbol,timeframe,status,rows,detail\n")
    total = len(universe) * len(args.timeframes)
    done = 0
    for item in universe:
        symbol, tick = item["SECID"], float(item.get("MINSTEP") or 0)
        for timeframe in args.timeframes:
            done += 1
            target = args.out / timeframe / f"{symbol}.csv"
            if target.exists():
                status, count, detail = "complete_previous", 0, ""
            else:
                try:
                    bars = load_bars(symbol, timeframe)
                    if len(bars) < 250:
                        raise ValueError(f"insufficient_bars:{len(bars)}")
                    rows = evaluate(symbol, timeframe, bars, tick, specs)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    temp = target.with_suffix(".tmp")
                    with temp.open("w", newline="", encoding="utf-8") as stream:
                        writer = csv.DictWriter(stream, fieldnames=FIELDS)
                        writer.writeheader()
                        writer.writerows(rows)
                    temp.replace(target)
                    status, count, detail = "complete", len(rows), ""
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    status, count, detail = "skipped", 0, str(exc).replace(",", ";")
            with progress.open("a", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow((symbol, timeframe,status,count,detail))
            print(f"[{done}/{total}] {symbol} {timeframe}: {status} rows={count} {detail}", flush=True)
    print(f"Finished: {progress}", flush=True)


if __name__ == "__main__":
    run()
