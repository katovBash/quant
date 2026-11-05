"""Causal OHLCV interpretations of sourced trader ideas, not their personal systems."""

from __future__ import annotations

import math

from src.ema.core.scan_ema import ema


def _baseline(bars):
    signals = [0] * len(bars)
    for i in range(33, len(bars)):
        if bars[i]["ts"][:10] >= "2024-01-01":
            signals[i - 1] = 1
            break
    return signals, [0] * len(bars)


def _sma(values, length):
    out = [math.nan] * len(values)
    running = 0.0
    for i, value in enumerate(values):
        running += value
        if i >= length:
            running -= values[i - length]
        if i >= length - 1:
            out[i] = running / length
    return out


def _bands(bars, length):
    closes = [b["close"] for b in bars]
    middle = _sma(closes, length)
    upper, lower, width = [], [], []
    for i, center in enumerate(middle):
        if not math.isfinite(center):
            upper.append(math.nan); lower.append(math.nan); width.append(math.nan)
            continue
        dev = math.sqrt(sum((x - center) ** 2 for x in closes[i - length + 1:i + 1]) / length)
        upper.append(center + 2 * dev)
        lower.append(center - 2 * dev)
        width.append(4 * dev / center if center else math.nan)
    return middle, upper, lower, width


def _avwap(bars, length):
    out = [math.nan] * len(bars)
    for i in range(length, len(bars)):
        anchor = min(range(i - length, i), key=lambda j: bars[j]["low"])
        segment = bars[anchor:i + 1]
        volume = sum(max(float(b["volume"]), 0) for b in segment)
        if volume:
            out[i] = sum(((b["high"] + b["low"] + b["close"]) / 3) *
                         max(float(b["volume"]), 0) for b in segment) / volume
    return out


def signals(method: str, bars: list[dict], lookback: int):
    """Return close-confirmed entries and exits. All reference windows are past-only."""
    n = len(bars)
    if method == "baseline":
        return _baseline(bars)
    entry, exits = [0] * n, [0] * n
    closes = [b["close"] for b in bars]
    if method in {"bollinger-squeeze-breakout", "bollinger-confirmed-breakout"}:
        mid, upper, lower, bandwidth = _bands(bars, lookback)
        for i in range(lookback + 21, n):
            if method == "bollinger-squeeze-breakout":
                compressed = bandwidth[i - 1] <= min(bandwidth[i - 21:i])
                up = compressed and closes[i] > upper[i] and closes[i - 1] <= upper[i - 1]
                down = compressed and closes[i] < lower[i] and closes[i - 1] >= lower[i - 1]
            else:
                up = closes[i] > upper[i] and closes[i - 1] > upper[i - 1]
                down = closes[i] < lower[i] and closes[i - 1] < lower[i - 1]
            entry[i] = 1 if up else -1 if down else 0
            exits[i] = -1 if closes[i] < mid[i] else 1 if closes[i] > mid[i] else 0
    elif method in {"shannon-avwap-reclaim", "shannon-avwap-bounce"}:
        level = _avwap(bars, lookback)
        for i in range(lookback + 1, n):
            if not math.isfinite(level[i - 1]) or not math.isfinite(level[i]):
                continue
            if method == "shannon-avwap-reclaim":
                entry[i] = 1 if closes[i - 1] <= level[i - 1] and closes[i] > level[i] else 0
            else:
                entry[i] = 1 if bars[i]["low"] <= level[i] and closes[i] > level[i] and level[i] > level[i - 1] else 0
            exits[i] = -1 if closes[i] < level[i] else 0
    elif method in {"gerchik-false-breakout", "gerchik-level-retest"}:
        for i in range(lookback + 1, n):
            prior = bars[i - lookback:i]
            top = max(b["high"] for b in prior)
            bottom = min(b["low"] for b in prior)
            if method == "gerchik-false-breakout":
                entry[i] = 1 if bars[i]["low"] < bottom and closes[i] > bottom else -1 if bars[i]["high"] > top and closes[i] < top else 0
            else:
                earlier = bars[i - lookback - 1:i - 1]
                old_top = max(b["high"] for b in earlier)
                old_bottom = min(b["low"] for b in earlier)
                entry[i] = 1 if closes[i - 1] > old_top and bars[i]["low"] <= old_top and closes[i] > old_top else -1 if closes[i - 1] < old_bottom and bars[i]["high"] >= old_bottom and closes[i] < old_bottom else 0
            center = (top + bottom) / 2
            exits[i] = -1 if closes[i] < center else 1 if closes[i] > center else 0
    elif method == "elder-force-index":
        force = [0.0] + [(closes[i] - closes[i - 1]) * float(bars[i]["volume"]) for i in range(1, n)]
        smooth = ema(force, lookback)
        trend = ema(closes, 50)
        for i in range(51, n):
            entry[i] = 1 if smooth[i - 1] <= 0 < smooth[i] and closes[i] > trend[i] else -1 if smooth[i - 1] >= 0 > smooth[i] and closes[i] < trend[i] else 0
            exits[i] = -1 if smooth[i] < 0 else 1 if smooth[i] > 0 else 0
    elif method in {"oneil-flat-base", "oneil-double-bottom", "oneil-cup-handle"}:
        volumes = [float(b["volume"]) for b in bars]
        vol_avg = _sma(volumes, 50)
        trend = _sma(closes, 20)
        for i in range(max(lookback + 1, 51), n):
            base = bars[i - lookback:i]
            high = max(b["high"] for b in base)
            low = min(b["low"] for b in base)
            depth = (high - low) / high if high else 1
            volume_ok = volumes[i] >= 1.4 * vol_avg[i - 1]
            if method == "oneil-flat-base":
                form = depth <= 0.15
            elif method == "oneil-double-bottom":
                half = lookback // 2
                low1 = min(b["low"] for b in base[:half])
                low2 = min(b["low"] for b in base[half:])
                middle_high = max(b["high"] for b in base[half // 2:half + half // 2])
                form = depth <= 0.4 and abs(low1 - low2) / max(low1, low2) <= 0.08 and middle_high >= 1.08 * max(low1, low2)
            else:
                handle = base[-max(5, lookback // 5):]
                handle_high = max(b["high"] for b in handle)
                handle_low = min(b["low"] for b in handle)
                form = 0.15 <= depth <= 0.35 and (handle_high - handle_low) / handle_high <= 0.15
                high = handle_high
            entry[i] = 1 if form and volume_ok and closes[i] > high else 0
            exits[i] = -1 if closes[i] < trend[i] else 0
    else:
        raise ValueError(f"unknown trader method: {method}")
    return entry, exits
