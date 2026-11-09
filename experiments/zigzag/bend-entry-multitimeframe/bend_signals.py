"""Causal Band-ZigZag bend entries on completed OHLC candles.

The imported Trendoscope sticky/adaptive band library is not reproduced. This
experiment fixes an explicit BB20 formula and varies only observable entries.
"""

from __future__ import annotations

import math


TRIGGERS = ("same", "close", "break")
RATIOS = {"r0": 0.0, "r100": 1.0}
WICKS = {"w0": 0.0, "w50": 0.5}


def prepare(bars: list[dict]) -> list[dict]:
    closes = [float(bar["close"]) for bar in bars]
    records: list[dict] = []
    side = 0
    pivot_bar = -1
    pivot_price = 0.0
    previous_price = None
    previous_previous_price = None
    pivot_wick = 0.0
    pivot_excursion = 0.0
    for i, bar in enumerate(bars):
        high = float(bar["high"])
        low = float(bar["low"])
        opening = float(bar["open"])
        closing = closes[i]
        upper = lower = None
        if i >= 19:
            window = closes[i - 19:i + 1]
            middle = sum(window) / 20
            std = math.sqrt(sum((value - middle) ** 2 for value in window) / 20)
            upper, lower = middle + 2 * std, middle - 2 * std
        high_touch = upper is not None and high >= upper
        low_touch = lower is not None and low <= lower
        changed = False
        if high_touch != low_touch:
            new_side = 1 if high_touch else -1
            price = high if high_touch else low
            if new_side != side:
                previous_previous_price, previous_price = previous_price, (pivot_price if side else None)
                side, pivot_bar, pivot_price = new_side, i, price
                changed = True
            elif (side == 1 and price > pivot_price) or (side == -1 and price < pivot_price):
                pivot_bar, pivot_price = i, price
                changed = True
            if changed:
                span = high - low
                pivot_wick = ((high - max(opening, closing)) if side == 1
                              else (min(opening, closing) - low)) / span if span > 0 else 0.0
                pivot_excursion = ((high - upper) if side == 1 else (lower - low)) / closing if closing else 0.0
        ratio = None
        if previous_price is not None and previous_previous_price is not None:
            denominator = abs(previous_price - previous_previous_price)
            if denominator > 0:
                ratio = abs(pivot_price - previous_price) / denominator
        records.append({"side": side, "pivot_bar": pivot_bar, "changed": changed,
                        "ratio": ratio, "wick": pivot_wick,
                        "excursion_pct": 100 * pivot_excursion,
                        "upper": upper, "lower": lower})
    return records


def candidate_direction(trigger: str, bars: list[dict], records: list[dict], i: int,
                        delay: int) -> int:
    rec = records[i]
    side = rec["side"]
    if not side or i == 0:
        return 0
    bar = bars[i]
    previous = bars[i - 1]
    if trigger == "same" and delay == 0:
        if not rec["changed"]:
            return 0
        if side == 1 and float(bar["close"]) < float(bar["open"]) and float(bar["close"]) < rec["upper"]:
            return -1
        if side == -1 and float(bar["close"]) > float(bar["open"]) and float(bar["close"]) > rec["lower"]:
            return 1
    elif trigger != "same" and i - rec["pivot_bar"] == delay:
        if trigger == "close":
            if side == 1 and float(bar["close"]) < float(bar["open"]) and float(bar["close"]) < float(previous["close"]):
                return -1
            if side == -1 and float(bar["close"]) > float(bar["open"]) and float(bar["close"]) > float(previous["close"]):
                return 1
        elif trigger == "break":
            if side == 1 and float(bar["close"]) < float(previous["low"]):
                return -1
            if side == -1 and float(bar["close"]) > float(previous["high"]):
                return 1
    return 0


def signals_for_variant(variant: str, bars: list[dict], records: list[dict] | None = None):
    _, trigger, delay_code, ratio_code, wick_code = variant.split("__")
    delay = int(delay_code[1:])
    if (trigger not in TRIGGERS or ratio_code not in RATIOS or wick_code not in WICKS
            or not 0 <= delay <= 20 or (trigger == "same") != (delay == 0)):
        raise ValueError(variant)
    records = records if records is not None else prepare(bars)
    entries = [0] * len(bars)
    exits = [0] * len(bars)
    used_pivot = -1
    for i, rec in enumerate(records):
        direction = candidate_direction(trigger, bars, records, i, delay)
        if not direction or rec["pivot_bar"] == used_pivot:
            continue
        if (ratio_code != "r0" and (rec["ratio"] is None or rec["ratio"] < RATIOS[ratio_code])):
            continue
        if rec["wick"] < WICKS[wick_code]:
            continue
        entries[i] = direction
        used_pivot = rec["pivot_bar"]
    return entries, exits


def context_factory(_symbol: str, _timeframe: str):
    cached = None

    def factory(variant: str, bars: list[dict]):
        nonlocal cached
        if cached is None:
            cached = prepare(bars)
        return signals_for_variant(variant, bars, cached)

    return factory


def forward_events(bars: list[dict], records: list[dict], *, symbol: str, timeframe: str):
    """Exploratory outcomes after entry; never fed back into the signal grid."""
    for i in range(20, len(bars) - 11):
        age = i - records[i]["pivot_bar"]
        triggers = (("same", 0),) if age == 0 else (("close", age), ("break", age)) if 1 <= age <= 20 else ()
        for trigger, delay in triggers:
            direction = candidate_direction(trigger, bars, records, i, delay)
            if not direction:
                continue
            entry = float(bars[i + 1]["open"])
            if entry <= 0:
                continue
            rec = records[i]
            yield {"symbol": symbol, "timeframe": timeframe, "trigger": trigger,
                   "delay_bars": delay, "signal_date": bars[i]["ts"], "direction": direction,
                   "leg_ratio": rec["ratio"], "wick_fraction": round(rec["wick"], 6),
                   "band_excursion_pct": round(rec["excursion_pct"], 6),
                   "forward_3bar_pct": round(100 * direction * (float(bars[i + 3]["close"]) / entry - 1), 6),
                   "forward_10bar_pct": round(100 * direction * (float(bars[i + 10]["close"]) / entry - 1), 6)}
