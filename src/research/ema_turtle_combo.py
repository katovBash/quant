"""Causal alignment of completed higher-timeframe EMA events with Turtle bars."""

from __future__ import annotations

from bisect import bisect_left


def align_confirmed_events(source_bars: list[dict], source_events: list[int],
                           target_bars: list[dict], *, same_timeframe: bool) -> list[int]:
    """Use a source signal only when its bar has closed (next source bar opens)."""
    if len(source_bars) != len(source_events):
        raise ValueError("source candle and signal lengths differ")
    if same_timeframe:
        if len(target_bars) != len(source_bars):
            raise ValueError("same-timeframe candle lengths differ")
        return source_events.copy()
    target_stamps = [bar["ts"] for bar in target_bars]
    aligned = [0] * len(target_bars)
    for index, event in enumerate(source_events[:-1]):
        if event:
            # The next source bar begins only after this complete source bar.
            available = source_bars[index + 1]["ts"]
            lower_index = bisect_left(target_stamps, available)
            if lower_index < len(target_bars):
                aligned[lower_index] = event
    return aligned


def latest_direction(events: list[int]) -> list[int]:
    state = 0
    result = []
    for event in events:
        if event:
            state = event
        result.append(state)
    return result


def recent_matching_gate(trigger: list[int], confirmation: list[int],
                         max_age: int = 3) -> tuple[list[bool], list[bool]]:
    last_up = last_down = -10**9
    up, down = [], []
    for index, (event, confirm) in enumerate(zip(trigger, confirmation)):
        if confirm > 0:
            last_up = index
        elif confirm < 0:
            last_down = index
        up.append(event > 0 and index - last_up <= max_age)
        down.append(event < 0 and index - last_down <= max_age)
    return up, down


def state_gate(trigger: list[int], confirmation: list[int]) -> tuple[list[bool], list[bool]]:
    state = latest_direction(confirmation)
    return ([event > 0 and state[index] > 0 for index, event in enumerate(trigger)],
            [event < 0 and state[index] < 0 for index, event in enumerate(trigger)])
