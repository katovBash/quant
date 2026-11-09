"""Past-only confirmed ZigZag pivots and level-breakout signals."""

from __future__ import annotations


def confirmed_pivots(bars: list[dict], wing: int, deviation_pct: float):
    """Yield (confirmation index, pivot index, side, price) without backdating events."""
    if wing < 1 or deviation_pct <= 0:
        raise ValueError("positive wing and reversal deviation required")
    last_side = None
    last_price = None
    for i in range(2 * wing, len(bars)):
        center = i - wing
        previous = bars[center - wing:center]
        following = bars[center + 1:i + 1]
        high = bars[center]["high"]
        low = bars[center]["low"]
        high_ok = high > max(bar["high"] for bar in previous) and high >= max(
            bar["high"] for bar in following)
        low_ok = low < min(bar["low"] for bar in previous) and low <= min(
            bar["low"] for bar in following)
        for side, price, valid in (("high", high, high_ok), ("low", low, low_ok)):
            if not valid:
                continue
            if last_side is None or (side == last_side and
                                     (price > last_price if side == "high" else price < last_price)):
                last_side, last_price = side, price
                yield i, center, side, price
            elif side != last_side and 100 * abs(price / last_price - 1) >= deviation_pct:
                last_side, last_price = side, price
                yield i, center, side, price


def breakout_signals(bars: list[dict], wing: int, deviation_pct: float):
    """Signal on close after crossing a level known before the current bar."""
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    last_high = last_low = None
    for i in range(1, n):
        close, previous_close = bars[i]["close"], bars[i - 1]["close"]
        if last_high is not None and previous_close <= last_high < close:
            entries[i] = 1
        elif last_low is not None and previous_close >= last_low > close:
            entries[i] = -1
        if last_low is not None and close < last_low:
            exits[i] = -1
        elif last_high is not None and close > last_high:
            exits[i] = 1
        while pending is not None and pending[0] == i:
            _, _, side, price = pending
            if side == "high":
                last_high = price
            else:
                last_low = price
            pending = next(pivots, None)
    return entries, exits


def retest_signals(bars: list[dict], wing: int, deviation_pct: float,
                   zone_pct: float):
    """One entry on the first post-breakout retest of a known pivot level."""
    if zone_pct < 0:
        raise ValueError("zone_pct must be nonnegative")
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    last_high = last_low = None
    armed_high = armed_low = None
    armed_high_at = armed_low_at = -1
    for i in range(1, n):
        bar, previous_close = bars[i], bars[i - 1]["close"]
        close = bar["close"]
        if armed_high is not None and i > armed_high_at and (
                bar["low"] <= armed_high * (1 + zone_pct / 100)
                and bar["low"] >= armed_high * (1 - zone_pct / 100)
                and close > armed_high):
            entries[i] = 1
            armed_high = None
        elif armed_low is not None and i > armed_low_at and (
                bar["high"] >= armed_low * (1 - zone_pct / 100)
                and bar["high"] <= armed_low * (1 + zone_pct / 100)
                and close < armed_low):
            entries[i] = -1
            armed_low = None
        if last_high is not None and close < last_high:
            exits[i] = -1
        elif last_low is not None and close > last_low:
            exits[i] = 1
        if last_high is not None and previous_close <= last_high < close:
            armed_high, armed_high_at = last_high, i
            armed_low = None
        if last_low is not None and previous_close >= last_low > close:
            armed_low, armed_low_at = last_low, i
            armed_high = None
        while pending is not None and pending[0] == i:
            _, _, side, price = pending
            if side == "high":
                last_high = price
                armed_high = None
            else:
                last_low = price
                armed_low = None
            pending = next(pivots, None)
    return entries, exits


def _line(points: list[tuple[int, float]], at: int):
    if len(points) < 2:
        return None
    (i0, p0), (i1, p1) = points[-2:]
    if i1 <= i0:
        return None
    return p1 + (p1 - p0) * (at - i1) / (i1 - i0)


def trendline_signals(bars: list[dict], wing: int, deviation_pct: float,
                      max_age: int):
    """Cross the line through two already confirmed same-side pivots."""
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    highs, lows = [], []
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    for i in range(1, n):
        high_line = _line(highs, i)
        low_line = _line(lows, i)
        high_previous = _line(highs, i - 1)
        low_previous = _line(lows, i - 1)
        if (high_line is not None and high_previous is not None
                and i - highs[-1][0] <= max_age and high_line > 0
                and bars[i - 1]["close"] <= high_previous
                and bars[i]["close"] > high_line):
            entries[i] = 1
        elif (low_line is not None and low_previous is not None
              and i - lows[-1][0] <= max_age and low_line > 0
              and bars[i - 1]["close"] >= low_previous
              and bars[i]["close"] < low_line):
            entries[i] = -1
        exits[i] = entries[i]
        while pending is not None and pending[0] == i:
            _, center, side, price = pending
            (highs if side == "high" else lows).append((center, price))
            pending = next(pivots, None)
    return entries, exits


def third_touch_signals(bars: list[dict], wing: int, deviation_pct: float,
                        zone_pct: float, max_age: int, style: str,
                        line_bars: list[dict] | None = None,
                        exit_mode: str = "opposite_signal", start: str = "2024-01-01",
                        slope_mode: str = "any"):
    """Trade the first post-confirmation third contact with a two-pivot line.

    Support and resistance are both considered. Bounce trades away from the
    line; breakout trades through it. Signals are decided at bar close and the
    shared simulator fills at the next open.
    """
    if style not in ("bounce", "breakout") or zone_pct <= 0 or max_age < 1:
        raise ValueError("invalid third-touch settings")
    if exit_mode not in ("opposite_signal", "opposite_line", "tp_3", "tp_5", "tp_8",
                         "tp_atr_2", "tp_atr_4"):
        raise ValueError("invalid third-touch exit mode")
    if slope_mode not in ("any", "trend"):
        raise ValueError("invalid third-touch slope mode")
    local_lines = line_bars is None
    line_bars = bars if line_bars is None else line_bars
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    points = {"high": [], "low": []}
    used = set()
    broken = set()
    pivots = iter(confirmed_pivots(line_bars, wing, deviation_pct))
    pending = next(pivots, None)
    completed_higher = 0
    previous_coordinate = 0
    tracked_position = 0
    entry_price = None
    entry_atr = None
    for i in range(1, n):
        if exit_mode != "opposite_signal" and bars[i]["ts"][:10] >= start:
            previous_exit = exits[i - 1]
            previous_entry = entries[i - 1]
            if tracked_position and previous_exit and (tracked_position > 0) != (previous_exit > 0):
                tracked_position, entry_price, entry_atr = 0, None, None
            if previous_entry and (not tracked_position or (tracked_position > 0) != (previous_entry > 0)):
                tracked_position, entry_price = previous_entry, bars[i]["open"]
                if exit_mode.startswith("tp_atr_") and i >= 15:
                    ranges = []
                    for j in range(i - 14, i):
                        previous_close = bars[j - 1]["close"]
                        candle = bars[j]
                        ranges.append(max(candle["high"] - candle["low"],
                                          abs(candle["high"] - previous_close),
                                          abs(candle["low"] - previous_close)))
                    entry_atr = sum(ranges) / 14
        if local_lines:
            coordinate, prior_coordinate = i, i - 1
        else:
            signal_day = bars[i]["ts"][:10]
            while (completed_higher < len(line_bars)
                   and line_bars[completed_higher]["ts"][:10] < signal_day):
                completed_higher += 1
            coordinate, prior_coordinate = completed_higher, previous_coordinate
            while pending is not None and pending[0] < completed_higher:
                confirmed_at, center, side, price = pending
                points[side].append((center, price, confirmed_at))
                pending = next(pivots, None)
        signals = []
        levels = {}
        for side in ("high", "low"):
            anchors = points[side]
            if len(anchors) < 2:
                continue
            (first_i, first_price, _), (second_i, second_price, confirmed_at) = anchors[-2:]
            key = (side, first_i, second_i)
            if (coordinate <= confirmed_at or coordinate - second_i > max_age
                    or second_i == first_i):
                continue
            slope = (second_price - first_price) / (second_i - first_i)
            level = second_price + slope * (coordinate - second_i)
            previous = second_price + slope * (prior_coordinate - second_i)
            if level <= 0 or previous <= 0:
                continue
            levels[side] = level
            if slope_mode == "trend" and ((side == "low" and slope <= 0) or
                                           (side == "high" and slope >= 0)):
                continue
            if key in used:
                continue
            bar, prior = bars[i], bars[i - 1]
            tolerance = level * zone_pct / 100
            if side == "low":
                approaching = prior["close"] >= previous
                touched = bar["low"] <= level + tolerance
                bounce = (key not in broken and touched
                          and bar["low"] >= level - tolerance and bar["close"] > level)
                breakout = touched and bar["close"] < level - tolerance
                direction = 1 if style == "bounce" else -1
                violated = bar["close"] < level - tolerance
            else:
                approaching = prior["close"] <= previous
                touched = bar["high"] >= level - tolerance
                bounce = (key not in broken and touched
                          and bar["high"] <= level + tolerance and bar["close"] < level)
                breakout = touched and bar["close"] > level + tolerance
                direction = -1 if style == "bounce" else 1
                violated = bar["close"] > level + tolerance
            if approaching and (bounce if style == "bounce" else breakout):
                signals.append((key, direction))
            if violated:
                broken.add(key)
        if len(signals) == 1:
            key, direction = signals[0]
            entries[i] = exits[i] = direction
            used.add(key)
        elif signals:
            used.update(key for key, _ in signals)
        if exit_mode != "opposite_signal" and tracked_position and not entries[i]:
            bar = bars[i]
            if exit_mode == "opposite_line":
                opposite = levels.get("high" if tracked_position > 0 else "low")
                reachable = (opposite is not None and
                             (opposite > entry_price * (1 + zone_pct / 100)
                              if tracked_position > 0 else
                              opposite < entry_price * (1 - zone_pct / 100)))
                reached = (reachable and
                           (bar["high"] >= opposite * (1 - zone_pct / 100)
                            if tracked_position > 0 else
                            bar["low"] <= opposite * (1 + zone_pct / 100)))
            elif exit_mode.startswith("tp_atr_"):
                multiple = int(exit_mode.rsplit("_", 1)[1])
                reached = (entry_atr is not None and
                           (bar["high"] >= entry_price + multiple * entry_atr
                            if tracked_position > 0 else
                            bar["low"] <= entry_price - multiple * entry_atr))
            else:
                target = float(exit_mode.split("_")[1]) / 100
                reached = (bar["high"] >= entry_price * (1 + target)
                           if tracked_position > 0 else
                           bar["low"] <= entry_price * (1 - target))
            if reached:
                exits[i] = -tracked_position
        if local_lines:
            while pending is not None and pending[0] == i:
                confirmed_at, center, side, price = pending
                points[side].append((center, price, confirmed_at))
                pending = next(pivots, None)
        previous_coordinate = coordinate
    return entries, exits


def parallel_second_touch_signals(bars: list[dict], wing: int, deviation_pct: float,
                                  zone_pct: float, max_age: int,
                                  line_bars: list[dict] | None = None,
                                  exit_mode: str = "opposite_line",
                                  start: str = "2024-01-01"):
    """Second contact with a parallel channel, using only confirmed pivots.

    Two lows define support and the first later high anchors parallel resistance.
    A later resistance rejection opens short. The symmetric construction opens
    long from support. Confirmation bars are never backdated to pivot bars.
    """
    if zone_pct <= 0 or max_age < 1 or exit_mode not in ("opposite_line", "tp_3", "tp_5"):
        raise ValueError("invalid parallel channel settings")
    local = line_bars is None
    line_bars = bars if local else line_bars
    entries, exits = [0] * len(bars), [0] * len(bars)
    points = {"high": [], "low": []}
    pivots = iter(confirmed_pivots(line_bars, wing, deviation_pct))
    pending = next(pivots, None)
    used, broken = set(), set()
    completed_higher = 0
    previous_coordinate = 0
    position, entry_price, active_channel, pending_channel = 0, None, None, None

    for i in range(1, len(bars)):
        bar = bars[i]
        if position and exits[i - 1] == -position:
            position, entry_price, active_channel = 0, None, None
        if entries[i - 1]:
            position, entry_price = entries[i - 1], bar["open"]
            active_channel = pending_channel
        if local:
            coordinate, prior_coordinate = i, i - 1
        else:
            signal_day = bar["ts"][:10]
            while (completed_higher < len(line_bars)
                   and line_bars[completed_higher]["ts"][:10] < signal_day):
                completed_higher += 1
            coordinate, prior_coordinate = completed_higher, previous_coordinate
            while pending is not None and pending[0] < completed_higher:
                confirmed_at, center, side, price = pending
                points[side].append((center, price, confirmed_at))
                pending = next(pivots, None)

        candidates = []
        for anchor_side, direction in (("high", -1), ("low", 1)):
            line_side = "low" if anchor_side == "high" else "high"
            line_points = points[line_side]
            if len(line_points) < 2:
                continue
            first, second = line_points[-2:]
            anchors = [point for point in points[anchor_side] if point[0] > second[0]]
            if not anchors:
                continue
            anchor = anchors[0]
            key = (anchor_side, first[0], second[0], anchor[0])
            if (coordinate <= anchor[2] or coordinate - anchor[0] > max_age
                    or first[0] == second[0] or key in used or key in broken):
                continue
            slope = (second[1] - first[1]) / (second[0] - first[0])
            base_at_anchor = second[1] + slope * (anchor[0] - second[0])
            width = (anchor[1] - base_at_anchor if direction < 0
                     else base_at_anchor - anchor[1])
            if width <= 0 or width / anchor[1] < 0.01:
                continue
            base = second[1] + slope * (coordinate - second[0])
            previous_base = second[1] + slope * (prior_coordinate - second[0])
            lower = base if direction < 0 else base - width
            upper = base + width if direction < 0 else base
            boundary = upper if direction < 0 else lower
            previous_boundary = (previous_base + width if direction < 0
                                 else previous_base - width)
            if lower <= 0 or upper <= lower:
                continue
            tolerance = boundary * zone_pct / 100
            if direction < 0:
                touched = (bars[i - 1]["close"] <= previous_boundary
                           and boundary - tolerance <= bar["high"] <= boundary + tolerance
                           and bar["close"] < boundary)
                violated = bar["close"] > boundary + tolerance
            else:
                touched = (bars[i - 1]["close"] >= previous_boundary
                           and boundary - tolerance <= bar["low"] <= boundary + tolerance
                           and bar["close"] > boundary)
                violated = bar["close"] < boundary - tolerance
            if touched:
                candidates.append((key, direction, (second[0], second[1], slope, width, direction)))
            if violated:
                broken.add(key)
        if len(candidates) == 1 and bar["ts"][:10] >= start:
            key, direction, channel = candidates[0]
            entries[i] = exits[i] = direction
            pending_channel = channel
            used.add(key)
        elif candidates:
            used.update(item[0] for item in candidates)

        if position and not entries[i] and bar["ts"][:10] >= start:
            second_i, second_price, slope, width, direction = active_channel
            base = second_price + slope * (coordinate - second_i)
            lower = base if direction < 0 else base - width
            upper = base + width if direction < 0 else base
            if exit_mode == "opposite_line":
                target = lower if position < 0 else upper
                reached = (bar["low"] <= target if position < 0 else bar["high"] >= target)
            else:
                pct = int(exit_mode.split("_")[1]) / 100
                target = entry_price * (1 - pct if position < 0 else 1 + pct)
                reached = (bar["low"] <= target if position < 0 else bar["high"] >= target)
            stop = (bar["close"] > upper * (1 + zone_pct / 100) if position < 0
                    else bar["close"] < lower * (1 - zone_pct / 100))
            if reached or stop:
                exits[i] = -position
        if local:
            while pending is not None and pending[0] == i:
                confirmed_at, center, side, price = pending
                points[side].append((center, price, confirmed_at))
                pending = next(pivots, None)
        previous_coordinate = coordinate
    return entries, exits


def confirmed_channel_bounce_signals(
        bars: list[dict], wing: int, deviation_pct: float, zone_pct: float,
        max_age: int, exit_mode: str = "tp_5", confirm_mode: str = "inside",
        start: str = "2024-01-01", trace: list[dict] | None = None):
    """Trade rejection of a parallel channel made from two ZigZag pivots and one opposite pivot.

    Two highs and one low define a descending or rising channel; two lows and
    one high work symmetrically. The opposite anchor may lie between the two
    base pivots. Only pivots confirmed before the signal candle are available.
    A wick may cross the boundary, but the completed candle must close inside.
    """
    if (wing < 1 or deviation_pct <= 0 or zone_pct <= 0 or max_age < 1 or
            exit_mode not in ("tp_5", "tp_8", "opposite_line") or
            confirm_mode not in ("inside", "directional")):
        raise ValueError("invalid confirmed channel settings")
    entries, exits = [0] * len(bars), [0] * len(bars)
    points = {"high": [], "low": []}
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    used, broken = set(), set()
    position, entry_price, active_channel = 0, None, None
    for i in range(1, len(bars)):
        bar = bars[i]
        if position and exits[i - 1] == -position:
            position, entry_price, active_channel = 0, None, None
        if entries[i - 1]:
            position, entry_price = entries[i - 1], bar["open"]
            active_channel = previous_channel
        candidates = []
        for base_side in ("high", "low"):
            base = points[base_side]
            if len(base) < 2:
                continue
            first, second = base[-2:]
            other = points["low" if base_side == "high" else "high"]
            middle = [pivot for pivot in other if first[0] < pivot[0] < second[0]]
            later = [pivot for pivot in other if pivot[0] > second[0]]
            anchor = middle[-1] if middle else later[-1] if later else None
            if anchor is None or i <= max(second[2], anchor[2]) or (
                    i - max(second[0], anchor[0]) > max_age):
                continue
            slope = (second[1] - first[1]) / (second[0] - first[0])
            base_at_anchor = second[1] + slope * (anchor[0] - second[0])
            width = (base_at_anchor - anchor[1] if base_side == "high"
                     else anchor[1] - base_at_anchor)
            if width <= 0 or width / anchor[1] < 0.01:
                continue
            basis = second[1] + slope * (i - second[0])
            upper = basis if base_side == "high" else basis + width
            lower = basis - width if base_side == "high" else basis
            if lower <= 0 or upper <= lower:
                continue
            key = (base_side, first[0], second[0], anchor[0])
            candidates.append((max(second[2], anchor[2]), key, lower, upper,
                               (second[0], second[1], slope, width, base_side)))
        channel = max(candidates, key=lambda item: item[0]) if candidates else None
        if trace is not None:
            trace.append({"index": i, "lower": channel[2] if channel else None,
                          "upper": channel[3] if channel else None,
                          "base_side": channel[4][4] if channel else None})
        if channel is not None:
            _, key, lower, upper, geometry = channel
            prior = bars[i - 1]["close"]
            slope = geometry[2]
            inside_prior = lower - slope <= prior <= upper - slope
            inside_close = lower < bar["close"] < upper
            support = (inside_prior and inside_close and
                       bar["low"] <= lower * (1 + zone_pct / 100) and
                       (confirm_mode == "inside" or bar["close"] > bar["open"]))
            resistance = (inside_prior and inside_close and
                          bar["high"] >= upper * (1 - zone_pct / 100) and
                          (confirm_mode == "inside" or bar["close"] < bar["open"]))
            if bar["ts"][:10] >= start and support != resistance:
                side = 1 if support else -1
                if (key, side) not in used and (key, side) not in broken:
                    entries[i] = exits[i] = side
                    previous_channel = geometry
                    used.add((key, side))
            if bar["close"] < lower * (1 - zone_pct / 100):
                broken.add((key, 1))
            if bar["close"] > upper * (1 + zone_pct / 100):
                broken.add((key, -1))
        if position and not entries[i] and bar["ts"][:10] >= start:
            second_i, second_price, slope, width, base_side = active_channel
            basis = second_price + slope * (i - second_i)
            upper = basis if base_side == "high" else basis + width
            lower = basis - width if base_side == "high" else basis
            if exit_mode == "opposite_line":
                reached = (bar["high"] >= upper if position > 0 else bar["low"] <= lower)
            else:
                target = int(exit_mode.split("_")[1]) / 100
                reached = (bar["high"] >= entry_price * (1 + target) if position > 0
                           else bar["low"] <= entry_price * (1 - target))
            stopped = (bar["close"] < lower * (1 - zone_pct / 100) if position > 0
                       else bar["close"] > upper * (1 + zone_pct / 100))
            if reached or stopped:
                exits[i] = -position
        while pending is not None and pending[0] == i:
            _, center, side, price = pending
            points[side].append((center, price, i))
            pending = next(pivots, None)
    return entries, exits


def compression_signals(bars: list[dict], wing: int, deviation_pct: float,
                        min_narrowing_pct: float):
    """Break a converging two-high/two-low pivot triangle after confirmation."""
    n = len(bars)
    entries, exits = [0] * n, [0] * n
    highs, lows = [], []
    pivots = iter(confirmed_pivots(bars, wing, deviation_pct))
    pending = next(pivots, None)
    for i in range(1, n):
        if len(highs) >= 2 and len(lows) >= 2:
            start = max(highs[-2][0], lows[-2][0])
            upper_start, lower_start = _line(highs, start), _line(lows, start)
            upper, lower = _line(highs, i), _line(lows, i)
            upper_previous, lower_previous = _line(highs, i - 1), _line(lows, i - 1)
            initial_width = upper_start - lower_start
            width = upper - lower
            converging = highs[-1][1] < highs[-2][1] and lows[-1][1] > lows[-2][1]
            if (converging and initial_width > 0 and width > 0 and upper > 0
                    and i - max(highs[-1][0], lows[-1][0]) <= 100
                    and 100 * (1 - width / initial_width) >= min_narrowing_pct):
                if bars[i - 1]["close"] <= upper_previous and bars[i]["close"] > upper:
                    entries[i] = 1
                elif bars[i - 1]["close"] >= lower_previous and bars[i]["close"] < lower:
                    entries[i] = -1
                exits[i] = entries[i]
        while pending is not None and pending[0] == i:
            _, center, side, price = pending
            (highs if side == "high" else lows).append((center, price))
            pending = next(pivots, None)
    return entries, exits
