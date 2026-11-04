"""Frozen EMA13/48 long+short signal for TV review on PLZL, VTBR and GAZP 1H.

Only completed closes are inputs. This module does not fetch quotes, size
positions, place orders, or join the active PLZL EMA12/33 paper account.
"""

from __future__ import annotations


FAST = 13
SLOW = 48
STRATEGY_ID = "ema-cross-13-48-long-short-1h"


def ema(values: list[float], period: int) -> list[float]:
    result: list[float] = []
    alpha = 2 / (period + 1)
    for value in values:
        result.append(value if not result else result[-1] + alpha * (value - result[-1]))
    return result


def target_side(closes: list[float], mode: str, position: int) -> str | None:
    """Return long, short, flat or None after the last completed candle."""
    if mode not in ("long", "short", "long_short"):
        raise ValueError(f"invalid mode: {mode}")
    if len(closes) < SLOW + 2:
        return None
    fast, slow = ema(closes, FAST), ema(closes, SLOW)
    up = fast[-2] <= slow[-2] and fast[-1] > slow[-1]
    down = fast[-2] >= slow[-2] and fast[-1] < slow[-1]
    if up:
        return "long" if mode in ("long", "long_short") else "flat" if position < 0 else None
    if down:
        return "short" if mode in ("short", "long_short") else "flat" if position > 0 else None
    return None
