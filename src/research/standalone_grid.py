"""Past-only single-indicator research on the fixed MOEX candle snapshot.

This evaluates RSI, ADX directional movement, four confirmed pivot lines, or
price/candle patterns *without EMA*. It uses the existing next-open simulator;
results are exploratory because short costs and exchange lots are incomplete.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from src.ema.core.adx_ema import adx, rma
from src.ema.core.compare_ema_filters import rsi, trendlines
from src.ema.core.research_ema_combinations import double_patterns, simulate
from src.ema.core.scan_ema import ema, four_hour
from src.research.timeframes import TIMEFRAMES, load_research_bars, sample_period
from src.research.manifest import update_manifest

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/moex_scan"
UNIVERSE = CACHE / "universe_2026-10-30.json"
FAMILIES = ("rsi", "adx", "four_point_levels", "patterns", "ema_levels")
MODES = ("long", "short", "long_short")
FIELDS = ("symbol", "timeframe", "indicator", "variant", "parameters", "mode", "bars",
          "first_bar", "last_bar", "closed_trades", "winning_trades", "win_rate_pct",
          "net_return_pct", "buy_hold_return_pct", "excess_vs_hold_pp", "profit_factor",
          "max_drawdown_pct", "late_trades", "late_wins", "late_return_pct",
          "late_buy_hold_pct", "late_profit_factor", "late_drawdown_pct")


def load_bars(symbol: str, timeframe: str) -> list[dict]:
    return load_research_bars(CACHE, symbol, timeframe)


def crossing(values: list[float], above: float, below: float) -> list[int]:
    """Momentum regime: long on rising above a threshold, short on falling below."""
    signals = [0] * len(values)
    for i in range(1, len(values)):
        prior, current = values[i - 1], values[i]
        if math.isfinite(prior) and math.isfinite(current):
            if prior <= above < current:
                signals[i] = 1
            elif prior >= below > current:
                signals[i] = -1
    return signals


def adx_direction(bars: list[dict], length: int, minimum: float) -> list[int]:
    """Cross of Wilder +DI/-DI when ADX is at least minimum."""
    tr, plus_dm, minus_dm = [], [], []
    for i, bar in enumerate(bars):
        if not i:
            tr.append(bar["high"] - bar["low"])
            plus_dm.append(0.0)
            minus_dm.append(0.0)
            continue
        prev = bars[i - 1]
        up, down = bar["high"] - prev["high"], prev["low"] - bar["low"]
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        tr.append(max(bar["high"] - bar["low"],
                      abs(bar["high"] - prev["close"]), abs(bar["low"] - prev["close"])))
    smooth_tr, smooth_plus, smooth_minus = rma(tr, length), rma(plus_dm, length), rma(minus_dm, length)
    strength = adx(bars, length)
    result = [0] * len(bars)
    for i in range(1, len(bars)):
        if not math.isfinite(strength[i]) or strength[i] < minimum:
            continue
        if not all(math.isfinite(x) for x in
                   (smooth_tr[i - 1], smooth_tr[i], smooth_plus[i - 1], smooth_plus[i],
                    smooth_minus[i - 1], smooth_minus[i])):
            continue
        if smooth_plus[i - 1] <= smooth_minus[i - 1] and smooth_plus[i] > smooth_minus[i]:
            result[i] = 1
        elif smooth_plus[i - 1] >= smooth_minus[i - 1] and smooth_plus[i] < smooth_minus[i]:
            result[i] = -1
    return result


def atr(bars: list[dict], length: int = 14) -> list[float]:
    ranges = []
    for i, bar in enumerate(bars):
        prev = bars[i - 1]["close"] if i else bar["close"]
        ranges.append(max(bar["high"] - bar["low"], abs(bar["high"] - prev), abs(bar["low"] - prev)))
    total = 0.0
    result = [math.nan] * len(bars)
    for i, value in enumerate(ranges):
        total += value
        if i >= length:
            total -= ranges[i - length]
        if i + 1 >= length:
            result[i] = total / length
    return result


def four_point_signals(bars: list[dict], wing: int, distance_atr: float) -> list[int]:
    """Bounce from two confirmed low pivots or two confirmed high pivots."""
    lines = trendlines(bars, wing)
    volatility = atr(bars)
    result = [0] * len(bars)
    previous_up = previous_down = False
    for i, (resistance, support) in enumerate(lines):
        valid = (math.isfinite(resistance) and math.isfinite(support) and
                 math.isfinite(volatility[i]) and resistance > support and
                 resistance - support >= 2 * volatility[i])
        bar = bars[i]
        up = valid and bar["low"] <= support + distance_atr * volatility[i] and bar["close"] > support
        down = valid and bar["high"] >= resistance - distance_atr * volatility[i] and bar["close"] < resistance
        if up and not previous_up and not down:
            result[i] = 1
        elif down and not previous_down and not up:
            result[i] = -1
        previous_up, previous_down = up, down
    return result


def ema_level_signals(bars: list[dict], period: int, distance_atr: float) -> list[int]:
    """First bounce against one EMA used as a dynamic support/resistance line."""
    levels = ema([bar["close"] for bar in bars], period)
    volatility = atr(bars)
    result = [0] * len(bars)
    previous_up = previous_down = False
    for index, (bar, level) in enumerate(zip(bars, levels)):
        valid = index >= max(period, 14) and math.isfinite(volatility[index])
        width = distance_atr * volatility[index] if valid else 0
        up = valid and level - width <= bar["low"] <= level + width and bar["close"] > level
        down = valid and level - width <= bar["high"] <= level + width and bar["close"] < level
        if up and not previous_up and not down:
            result[index] = 1
        elif down and not previous_down and not up:
            result[index] = -1
        previous_up, previous_down = up, down
    return result


def pattern_signals(bars: list[dict], kind: str, window: int = 0) -> list[int]:
    n = len(bars)
    up, down = [False] * n, [False] * n
    if kind == "breakout":
        for i in range(window, n):
            up[i] = bars[i]["close"] > max(bar["high"] for bar in bars[i - window:i])
            down[i] = bars[i]["close"] < min(bar["low"] for bar in bars[i - window:i])
    elif kind == "engulfing":
        for i in range(1, n):
            bar, previous = bars[i], bars[i - 1]
            up[i] = (previous["close"] < previous["open"] and bar["close"] > bar["open"] and
                     bar["open"] <= previous["close"] and bar["close"] >= previous["open"])
            down[i] = (previous["close"] > previous["open"] and bar["close"] < bar["open"] and
                       bar["open"] >= previous["close"] and bar["close"] <= previous["open"])
    elif kind == "hammer":
        for i, bar in enumerate(bars):
            body = max(abs(bar["close"] - bar["open"]), bar["close"] * 0.001)
            lower = min(bar["open"], bar["close"]) - bar["low"]
            upper = bar["high"] - max(bar["open"], bar["close"])
            up[i] = bar["close"] > bar["open"] and lower >= 2 * body and upper <= body
            down[i] = bar["close"] < bar["open"] and upper >= 2 * body and lower <= body
    elif kind == "double_confirmed":
        up, down = double_patterns(bars)
    else:
        raise ValueError(kind)
    return [1 if up[i] and (i == 0 or not up[i - 1]) and not down[i]
            else -1 if down[i] and (i == 0 or not down[i - 1]) and not up[i]
            else 0 for i in range(n)]


def variants(indicator: str, bars: list[dict], ema_periods=range(2, 667)):
    if indicator == "rsi":
        for length in (7, 14, 21):
            values = rsi(bars, length)
            for long_above, short_below in ((50, 50), (55, 45), (60, 40)):
                params = {"length": length, "long_above": long_above, "short_below": short_below}
                yield f"rsi_{length}_{long_above}_{short_below}", params, crossing(values, long_above, short_below)
    elif indicator == "adx":
        for length in (7, 14, 21):
            for minimum in (15, 20, 25, 30):
                params = {"length": length, "minimum": minimum}
                yield f"adx_di_{length}_{minimum}", params, adx_direction(bars, length, minimum)
    elif indicator == "four_point_levels":
        for wing in (2, 3, 5):
            for distance in (0.5, 1.0, 1.5):
                params = {"pivot_wing": wing, "distance_atr": distance}
                yield f"four_points_{wing}_{distance:g}", params, four_point_signals(bars, wing, distance)
    elif indicator == "patterns":
        for window in (10, 20, 40):
            yield f"breakout_{window}", {"pattern": "breakout", "window": window}, pattern_signals(bars, "breakout", window)
        for kind in ("engulfing", "hammer", "double_confirmed"):
            yield kind, {"pattern": kind}, pattern_signals(bars, kind)
    elif indicator == "ema_levels":
        for period in ema_periods:
            for distance in (0.25, 0.5, 1.0):
                params = {"period": period, "distance_atr": distance}
                yield f"ema_level_{period}_{distance:g}", params, ema_level_signals(bars, period, distance)
    else:
        raise ValueError(indicator)


def buy_hold_return(bars: list[dict], start: str, tick: float) -> float:
    eligible = [bar for bar in bars if bar["ts"][:10] >= start]
    if not eligible:
        return 0.0
    fee = 5 / 10_000
    first, last = eligible[0], eligible[-1]
    quantity = math.floor(1_000_000 * 0.25 / first["open"])
    cost = quantity * (first["open"] + tick) * (1 + fee)
    proceeds = quantity * max(last["close"] - tick, 0) * (1 - fee)
    return round(100 * (proceeds - cost) / 1_000_000, 2)


def evaluate(indicator: str, symbol: str, timeframe: str, bars: list[dict], tick: float,
             ema_periods=range(2, 667)) -> list[dict]:
    start, late_start = sample_period(timeframe)
    rows = []
    hold = buy_hold_return(bars, start, tick)
    late_hold = buy_hold_return(bars, late_start, tick)
    always = [True] * len(bars)
    never = [False] * len(bars)
    for variant, params, signals in variants(indicator, bars, ema_periods):
        for mode in MODES:
            up = never if mode == "short" else always
            down = never if mode == "long" else always
            whole = simulate(bars, signals, up, down, tick, start)
            late = simulate(bars, signals, up, down, tick, late_start)
            trades = whole["closed_trades"]
            rows.append({"symbol": symbol, "timeframe": timeframe, "indicator": indicator,
                         "variant": variant, "parameters": json.dumps(params, sort_keys=True), "mode": mode,
                         "bars": len(bars), "first_bar": bars[0]["ts"], "last_bar": bars[-1]["ts"],
                         "closed_trades": trades, "winning_trades": whole["winning_trades"],
                         "win_rate_pct": round(100 * whole["winning_trades"] / trades, 2) if trades else "",
                         "net_return_pct": whole["return_pct"], "buy_hold_return_pct": hold,
                         "excess_vs_hold_pp": round(whole["return_pct"] - hold, 2),
                         "profit_factor": whole["profit_factor"],
                         "max_drawdown_pct": whole["max_drawdown_pct"],
                         "late_trades": late["closed_trades"], "late_wins": late["winning_trades"],
                         "late_return_pct": late["return_pct"], "late_buy_hold_pct": late_hold,
                         "late_profit_factor": late["profit_factor"],
                         "late_drawdown_pct": late["max_drawdown_pct"]})
    return rows


def default_results_dir(indicator: str) -> Path:
    return ROOT / "experiments" / f"{indicator.replace('_', '-')}-grid-search" / "results"


def run(indicator: str, argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*")
    parser.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=TIMEFRAMES)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", type=Path, default=default_results_dir(indicator))
    parser.add_argument("--ema-period-min", type=int, default=2)
    parser.add_argument("--ema-period-max", type=int, default=666)
    args = parser.parse_args(argv)
    if indicator not in FAMILIES:
        raise ValueError(indicator)
    if args.ema_period_min < 2 or args.ema_period_max < args.ema_period_min:
        parser.error("EMA period range must satisfy 2 <= min <= max")
    ema_periods = range(args.ema_period_min, args.ema_period_max + 1)
    args.out.mkdir(parents=True, exist_ok=True)
    universe = [item for item in json.loads(UNIVERSE.read_text(encoding="utf-8"))
                if item.get("SECTYPE") in ("1", "2")]
    if args.symbols:
        wanted = set(args.symbols)
        universe = [item for item in universe if item["SECID"] in wanted]
    if args.limit:
        universe = universe[:args.limit]
    manifest = {"indicator": indicator, "combines_with_ema": False,
                "universe": str(UNIVERSE.relative_to(ROOT)), "snapshot": "2026-10-30",
                "symbols": [item["SECID"] for item in universe], "timeframes": args.timeframes,
                "fill": "signal on completed candle; next open plus/minus one tick; 25% equity; integer shares",
                "fee_bps_per_side": 5, "short_borrow_included": False,
                "late_start_by_timeframe": {tf: sample_period(tf)[1] for tf in args.timeframes},
                "late_period_is_independent": False,
                "minute_candles_required_for": [tf for tf in args.timeframes if tf in ("15M", "30M")]}
    if indicator == "ema_levels":
        manifest["ema_period_min"] = args.ema_period_min
        manifest["ema_period_max"] = args.ema_period_max
        manifest["zone_width_atr"] = [0.25, 0.5, 1.0]
    update_manifest(args.out / "manifest.json", manifest, protocol_keys=(
        "indicator", "combines_with_ema", "universe", "snapshot", "fill",
        "fee_bps_per_side", "short_borrow_included", "ema_period_min", "ema_period_max",
        "zone_width_atr"))
    progress = args.out / "progress.csv"
    if not progress.exists():
        progress.write_text("symbol,timeframe,status,rows,detail\n", encoding="utf-8")
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
                    rows = evaluate(indicator, symbol, timeframe, bars, tick, ema_periods)
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
                csv.writer(stream).writerow((symbol, timeframe, status, count, detail))
            print(f"[{done}/{total}] {symbol} {timeframe}: {status} rows={count} {detail}", flush=True)
    print(f"Finished {indicator}: {progress}", flush=True)
