from src.research.ema_turtle_combo import align_confirmed_events, recent_matching_gate, state_gate


def _bars(stamps):
    return [{"ts": stamp} for stamp in stamps]


def test_higher_signal_only_on_next_higher_bar():
    higher = _bars(["2026-01-01 09:00:00", "2026-01-01 13:00:00", "2026-01-01 18:00:00"])
    lower = _bars(["2026-01-01 09:00:00", "2026-01-01 10:00:00",
                   "2026-01-01 11:00:00", "2026-01-01 12:00:00",
                   "2026-01-01 13:00:00", "2026-01-01 14:00:00"])
    assert align_confirmed_events(higher, [1, -1, 1], lower, same_timeframe=False) == [0, 0, 0, 0, 1, 0]
    assert align_confirmed_events(higher[:2], [1, -1], lower[:5], same_timeframe=False) == [0, 0, 0, 0, 1]


def test_state_and_recent_confluence_are_directional():
    trigger = [0, 1, -1, 0, 1, 0, 0, 0, 1]
    confirmation = [1, 0, 0, -1, 0, 0, 0, 0, 0]
    up, down = state_gate(trigger, confirmation)
    assert up == [False, True, False, False, False, False, False, False, False]
    assert down[2] is False
    up, down = recent_matching_gate(trigger, confirmation, 3)
    assert up[1] is True and up[4] is False and up[8] is False
    assert down[2] is False
