"""Causal, mechanical adaptations of three published trader setups."""

from __future__ import annotations

import math

from src.ema.core.adx_ema import adx
from src.ema.core.compare_ema_filters import rsi
from src.ema.core.scan_ema import ema
from src.research.standalone_grid import atr


def sma(values: list[float], length: int) -> list[float]:
    out = [math.nan] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= length:
            total -= values[index - length]
        if index + 1 >= length:
            out[index] = total / length
    return out


def buy_hold(bars: list[dict], start: str) -> tuple[list[int], list[int]]:
    signals = [0] * len(bars)
    for index in range(33, len(bars)):
        if bars[index]["ts"][:10] >= start:
            signals[index - 1] = 1
            break
    return signals, [0] * len(bars)


def turtle(bars: list[dict], entry: int, exit_length: int) -> tuple[list[int], list[int]]:
    """Close-confirmed Donchian breakout; all windows exclude current bar."""
    signals = [0] * len(bars)
    exits = [0] * len(bars)
    for i in range(max(entry, exit_length), len(bars)):
        prior_entry = bars[i - entry:i]
        prior_exit = bars[i - exit_length:i]
        close = bars[i]["close"]
        if close > max(bar["high"] for bar in prior_entry):
            signals[i] = 1
        elif close < min(bar["low"] for bar in prior_entry):
            signals[i] = -1
        if close < min(bar["low"] for bar in prior_exit):
            exits[i] = -1
        elif close > max(bar["high"] for bar in prior_exit):
            exits[i] = 1
    return signals, exits


def connors(bars: list[dict], entry_rsi: int, exit_rsi: int = 70) -> tuple[list[int], list[int]]:
    """RSI2 oversold long above SMA200; overbought exit."""
    closes = [bar["close"] for bar in bars]
    trend = sma(closes, 200)
    momentum = rsi(bars, 2)
    signals = [0] * len(bars)
    exits = [0] * len(bars)
    for i in range(200, len(bars)):
        if closes[i] > trend[i] and momentum[i] < entry_rsi:
            signals[i] = 1
        if momentum[i] > exit_rsi:
            exits[i] = -1
    return signals, exits


def raschke(bars: list[dict], adx_threshold: int) -> tuple[list[int], list[int]]:
    """First EMA20 touch after ADX crosses threshold; long-only approximation."""
    closes = [bar["close"] for bar in bars]
    trend = ema(closes, 20)
    strength = adx(bars, 14)
    volatility = atr(bars, 14)
    signals = [0] * len(bars)
    exits = [0] * len(bars)
    armed_until = -1
    for i in range(34, len(bars)):
        if (math.isfinite(strength[i - 1]) and math.isfinite(strength[i])
                and strength[i - 1] <= adx_threshold < strength[i]
                and closes[i] > trend[i] > trend[i - 1]):
            armed_until = i + 10
        if (i <= armed_until and bars[i]["low"] <= trend[i] <= bars[i]["high"]
                and closes[i] > trend[i]):
            signals[i] = 1
            armed_until = -1
        if (closes[i] > max(bar["high"] for bar in bars[i - 20:i])
                or (math.isfinite(volatility[i])
                    and closes[i] < trend[i] - volatility[i])):
            exits[i] = -1
    return signals, exits


def all_signals(bars: list[dict], start: str) -> dict[str, tuple[list[int], list[int]]]:
    return {
        "baseline": buy_hold(bars, start),
        "dennis_turtle_20_10": turtle(bars, 20, 10),
        "dennis_turtle_55_20": turtle(bars, 55, 20),
        "connors_rsi2_5_70": connors(bars, 5, 70),
        "connors_rsi2_10_70": connors(bars, 10, 70),
        "raschke_grail_adx30": raschke(bars, 30),
        "raschke_grail_adx35": raschke(bars, 35),
    }
