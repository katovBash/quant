"""Causal price/RSI dual-swing experiment; adaptation, not author's Pine port."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.ema.core.compare_ema_filters import rsi
from src.research.parameter_grid import variants_from_grid
from src.research.trader_method_run import run
from src.research.zigzag_signals import breakout_signals, confirmed_pivots


def oscillator_pivots(values: list[float], wing: int):
    """Confirmed alternating RSI extrema, with a 3-point reversal threshold."""
    side, value = None, None
    for i in range(2 * wing, len(values)):
        center = i - wing
        window = values[center - wing:i + 1]
        if not all(math.isfinite(v) for v in window):
            continue
        current = values[center]
        high = current > max(window[:wing]) and current >= max(window[wing + 1:])
        low = current < min(window[:wing]) and current <= min(window[wing + 1:])
        for new_side, valid in (("high", high), ("low", low)):
            if not valid:
                continue
            if side is None or (new_side == side and
                                (current > value if side == "high" else current < value)):
                side, value = new_side, current
                yield i, center, side, value
            elif new_side != side and abs(current - value) >= 3:
                side, value = new_side, current
                yield i, center, side, value


def timed_exit(entries: list[int], bars: int):
    exits = [0] * len(entries)
    held, started = 0, -1
    for i, signal in enumerate(entries):
        if signal and signal != held:
            held, started = signal, i
        elif held and i - started >= bars:
            exits[i] = -held
            held, started = 0, -1
    return exits


def factory(_symbol: str, _timeframe: str):
    price_cache = {}
    osc_cache = {}
    rsi_cache = {}

    def signals(variant: str, bars: list[dict]):
        parts = variant.split("_")
        family = parts[0]
        if family == "price":
            wing, deviation = int(parts[1]), int(parts[2])
            return breakout_signals(bars, wing, deviation)
        if family == "osc":
            wing, length = int(parts[1]), int(parts[2])
            key = wing, length
            if key not in osc_cache:
                if length not in rsi_cache:
                    rsi_cache[length] = rsi(bars, length)
                values = rsi_cache[length]
                osc_cache[key] = list(oscillator_pivots(values, wing))
            entries = [0] * len(bars)
            for confirmed, _, side, _ in osc_cache[key]:
                entries[confirmed] = 1 if side == "low" else -1
            return entries, entries[:]
        _, pwing, deviation, o_length, design = parts
        pwing, deviation, o_length = int(pwing), int(deviation), int(o_length)
        o_wing = pwing
        pkey, okey = (pwing, deviation), (o_wing, o_length)
        if pkey not in price_cache:
            price_cache[pkey] = list(confirmed_pivots(bars, *pkey))
        if okey not in osc_cache:
            if o_length not in rsi_cache:
                rsi_cache[o_length] = rsi(bars, o_length)
            values = rsi_cache[o_length]
            osc_cache[okey] = list(oscillator_pivots(values, o_wing))
        price_events, _ = breakout_signals(bars, *pkey)
        entries = [0] * len(bars)
        if design.startswith("trend"):
            oscillator_side = None
            iterator = iter(osc_cache[okey])
            upcoming = next(iterator, None)
            for i in range(len(bars)):
                if price_events[i] and ((price_events[i] > 0 and oscillator_side == "low")
                                        or (price_events[i] < 0 and oscillator_side == "high")):
                    entries[i] = price_events[i]
                while upcoming and upcoming[0] == i:
                    oscillator_side = upcoming[2]
                    upcoming = next(iterator, None)
        else:
            by_price = {"high": [], "low": []}
            by_osc = {"high": [], "low": []}
            events = sorted([(event[0], 0, event) for event in price_cache[pkey]] +
                            [(event[0], 1, event) for event in osc_cache[okey]])
            for confirmed, source, event in events:
                _, center, side, value = event
                target = by_price if source == 0 else by_osc
                target[side].append((center, value, confirmed))
                if len(by_price[side]) < 2 or len(by_osc[side]) < 2:
                    continue
                (p0, pv0, _), (p1, pv1, pc) = by_price[side][-2:]
                (o0, ov0, _), (o1, ov1, oc) = by_osc[side][-2:]
                if abs(p1 - o1) > 2 * pwing or confirmed != max(pc, oc):
                    continue
                if side == "low" and pv1 < pv0 and ov1 > ov0:
                    entries[confirmed] = 1
                elif side == "high" and pv1 > pv0 and ov1 < ov0:
                    entries[confirmed] = -1
        exits = entries[:] if design.endswith("opp") else timed_exit(entries, 24)
        return entries, exits

    return signals


if __name__ == "__main__":
    experiment = Path(__file__).resolve().parent
    protocol = json.loads((experiment / "protocol.json").read_text())
    assert variants_from_grid(protocol["parameter_grid"]) == protocol["expected_variants"]
    run(experiment, smoke="--smoke" in sys.argv, context_factory=factory)
