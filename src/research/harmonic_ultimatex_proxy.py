"""Causal single-level XABCD proxy inspired by Trendoscope UltimateX.

This is not a reimplementation of the private UltimateX indicator.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.research.zigzag_signals import confirmed_pivots


@dataclass(frozen=True)
class Pattern:
    known_at: int
    key: tuple[int, ...]
    direction: int
    x: float
    a: float
    d: float
    stop: float | None = None


def _within(value: float, low: float, high: float, tolerance: float = 0.08) -> bool:
    return low * (1 - tolerance) <= value <= high * (1 + tolerance)


def _classify(points: list[tuple[int, str, float]], kind: str, known_at: int) -> Pattern | None:
    if len(points) < 5:
        return None
    tail = points[-5:]
    direction = 1 if tail[-1][1] == "low" else -1
    if [side for _, side, _ in tail] != (["low", "high", "low", "high", "low"] if direction > 0 else
                                        ["high", "low", "high", "low", "high"]):
        return None
    x, a, b, c, d = [price * direction for _, _, price in tail]
    if not (x < d < b < c < a and b > x):
        return None
    xa, ab, bc, cd = a - x, a - b, c - b, c - d
    if min(xa, ab, bc, cd) <= 0:
        return None
    ab_xa, bc_ab, cd_bc, xd_xa = ab / xa, bc / ab, cd / bc, (d - x) / xa
    if kind == "gartley":
        good = (_within(ab_xa, 0.618, 0.618) and _within(bc_ab, 0.382, 0.886)
                and _within(cd_bc, 1.272, 1.618) and _within(xd_xa, 1 - 0.786, 1 - 0.786))
    elif kind == "bat":
        good = (_within(ab_xa, 0.382, 0.5) and _within(bc_ab, 0.382, 0.886)
                and _within(cd_bc, 1.618, 2.618) and _within(xd_xa, 1 - 0.886, 1 - 0.886))
    else:
        raise ValueError(f"unknown pattern: {kind}")
    if not good:
        return None
    return Pattern(known_at, tuple(index for index, _, _ in tail), direction,
                   tail[0][2], tail[1][2], tail[4][2])


def detect_patterns(bars: list[dict], wing: int, kind: str) -> list[Pattern]:
    """Emit only when the D pivot has been confirmed, never at its plotted center."""
    points: list[tuple[int, str, float]] = []
    found: list[Pattern] = []
    seen: set[tuple[int, ...]] = set()
    for known_at, center, side, price in confirmed_pivots(bars, wing, 2):
        if points and points[-1][1] == side:
            points[-1] = (center, side, price)
            continue
        points.append((center, side, price))
        pattern = _classify(points, kind, known_at)
        if pattern and pattern.key not in seen:
            found.append(pattern)
            seen.add(pattern.key)
    return found


def pattern_signals(bars: list[dict], patterns: list[Pattern], entry_mode: str,
                    exit_mode: str) -> tuple[list[int], list[int]]:
    """State transitions decided at close; shared simulator fills next open."""
    if entry_mode not in {"detect", "retrace30"} or exit_mode not in {"tp", "time20"}:
        raise ValueError("unknown entry/exit mode")
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    by_bar: dict[int, list[Pattern]] = {}
    for pattern in patterns:
        by_bar.setdefault(pattern.known_at, []).append(pattern)
    pending: list[Pattern] = []
    active: Pattern | None = None
    scheduled: Pattern | None = None
    filled_at = -1

    def still_awaiting(pattern: Pattern, at: int) -> bool:
        """Reject patterns invalidated or completed before a tradable entry."""
        target = pattern.d + 0.618 * (pattern.a - pattern.d)
        stop = pattern.x if pattern.stop is None else pattern.stop
        for candle in bars[pattern.key[-1] + 1:at + 1]:
            if pattern.direction > 0:
                if candle["low"] <= stop or candle["high"] >= target:
                    return False
            elif candle["high"] >= stop or candle["low"] <= target:
                return False
        return True

    for i, bar in enumerate(bars):
        if i and exits[i - 1] and active:
            active = None
            filled_at = -1
        if i and entries[i - 1] and scheduled:
            active, scheduled, filled_at = scheduled, None, i
        pending.extend(by_bar.get(i, []))
        pending = [p for p in pending if i - p.known_at <= 20 and still_awaiting(p, i)]
        if active:
            direction = active.direction
            stop = active.x if active.stop is None else active.stop
            target = active.d + 0.618 * (active.a - active.d)
            stopped = bar["low"] <= stop if direction > 0 else bar["high"] >= stop
            targeted = bar["high"] >= target if direction > 0 else bar["low"] <= target
            timed = i - filled_at >= (40 if exit_mode == "tp" else 20)
            if stopped or timed or (exit_mode == "tp" and targeted):
                exits[i] = -direction
            continue
        if scheduled:
            continue
        if entry_mode == "detect":
            candidates = [p for p in by_bar.get(i, []) if still_awaiting(p, i)]
        else:
            candidates = [p for p in pending if i > p.known_at and
                          (bar["close"] >= p.d + 0.3 * (p.a - p.d) if p.direction > 0 else
                           bar["close"] <= p.d + 0.3 * (p.a - p.d))]
        if candidates:
            chosen = candidates[-1]
            entries[i] = chosen.direction
            scheduled = chosen
            pending = [p for p in pending if p.key != chosen.key]
    return entries, exits
