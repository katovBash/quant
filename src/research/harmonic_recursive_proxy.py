"""Declared five-pattern, two-level harmonic recognition experiment.

Recursive level 1 is an explicit causal adaptation, not private UltimateX code.
"""

from __future__ import annotations

from src.research.harmonic_ultimatex_proxy import Pattern, _classify, _within
from src.research.zigzag_signals import confirmed_pivots

KINDS = ("gartley", "bat", "butterfly", "crab", "deepcrab")
EXTENSION_KINDS = frozenset(("butterfly", "crab", "deepcrab"))


def pivot_events(bars: list[dict], wing: int, level: int) -> list[tuple[int, int, str, float]]:
    """Return (known bar, pivot center bar, side, price) at level 0 or 1."""
    if level not in (0, 1):
        raise ValueError("only levels 0 and 1 are declared")
    base = list(confirmed_pivots(bars, wing, 2))
    if level == 0:
        return base
    synthetic = [{"high": price, "low": price} for _, _, _, price in base]
    result = []
    for known_event, center_event, side, price in confirmed_pivots(synthetic, 2, 2):
        result.append((base[known_event][0], base[center_event][1], side, price))
    return result


def _extension(points: list[tuple[int, str, float]], kind: str,
               known_at: int) -> Pattern | None:
    tail = points[-5:]
    if len(tail) < 5:
        return None
    direction = 1 if tail[-1][1] == "low" else -1
    expected = ["low", "high", "low", "high", "low"] if direction > 0 else [
        "high", "low", "high", "low", "high"]
    if [side for _, side, _ in tail] != expected:
        return None
    x, a, b, c, d = [price * direction for _, _, price in tail]
    if not (d < x < b < c < a):
        return None
    xa, ab, bc, cd, ad = a - x, a - b, c - b, c - d, a - d
    if min(xa, ab, bc, cd, ad) <= 0:
        return None
    r_ab, r_bc, r_cd, r_ad = ab / xa, bc / ab, cd / bc, ad / xa
    ranges = {
        "butterfly": ((0.786, 0.786), (0.382, 0.886), (1.618, 2.618), (1.272, 1.618)),
        "crab": ((0.382, 0.618), (0.382, 0.886), (2.618, 3.618), (1.618, 1.618)),
        "deepcrab": ((0.886, 0.886), (0.382, 0.886), (2.0, 3.618), (1.618, 1.618)),
    }[kind]
    if not all(_within(value, lo, hi) for value, (lo, hi) in zip(
            (r_ab, r_bc, r_cd, r_ad), ranges)):
        return None
    original_x, original_a, original_d = tail[0][2], tail[1][2], tail[4][2]
    stop = original_d - direction * 0.10 * abs(original_a - original_d)
    if stop <= 0:
        return None
    return Pattern(known_at, tuple(index for index, _, _ in tail), direction,
                   original_x, original_a, original_d, stop)


def detect_from_events(events: list[tuple[int, int, str, float]], kind: str) -> list[Pattern]:
    if kind not in KINDS:
        raise ValueError(f"unknown pattern {kind}")
    points: list[tuple[int, str, float]] = []
    found: list[Pattern] = []
    seen: set[tuple[int, ...]] = set()
    for known_at, center, side, price in events:
        if points and points[-1][1] == side:
            points[-1] = (center, side, price)
            continue
        points.append((center, side, price))
        pattern = (_extension(points, kind, known_at) if kind in EXTENSION_KINDS else
                   _classify(points, kind, known_at))
        if pattern and pattern.key not in seen:
            found.append(pattern)
            seen.add(pattern.key)
    return found


def union_patterns(by_kind: dict[str, list[Pattern]]) -> list[Pattern]:
    """One event per XABCD geometry, with fixed family priority."""
    unique: dict[tuple[int, ...], Pattern] = {}
    for kind in KINDS:
        for pattern in by_kind[kind]:
            unique.setdefault(pattern.key, pattern)
    return sorted(unique.values(), key=lambda p: (p.known_at, p.key))
