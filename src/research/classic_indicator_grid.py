"""Causal, explicitly specified research rules for nine indicator families.

These are mechanical hypotheses built from published indicator definitions, not
claims about their creators' personal trading systems. Decisions use completed
bars; the shared simulator executes at the next bar open.
"""

from __future__ import annotations

from collections import deque


def _sma(values, length):
    out = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += value
        if i >= length:
            total -= values[i - length]
        if i >= length - 1:
            out[i] = total / length
    return out


def _ema(values, length):
    out = [None] * len(values)
    alpha = 2 / (length + 1)
    current = None
    for i, value in enumerate(values):
        current = value if current is None else current + alpha * (value - current)
        if i >= length - 1:
            out[i] = current
    return out


def _rma(values, length):
    out = [None] * len(values)
    current = None
    for i, value in enumerate(values):
        if i == length - 1:
            current = sum(values[:length]) / length
        elif i >= length:
            current += (value - current) / length
        if current is not None:
            out[i] = current
    return out


def _rolling_extreme(values, length, maximum):
    out = [None] * len(values)
    indices = deque()
    for i, value in enumerate(values):
        while indices and (values[indices[-1]] <= value if maximum else values[indices[-1]] >= value):
            indices.pop()
        indices.append(i)
        while indices[0] <= i - length:
            indices.popleft()
        if i >= length - 1:
            out[i] = (values[indices[0]], indices[0])
    return out


def _cross(values, upper, lower):
    out = [0] * len(values)
    for i in range(1, len(values)):
        a, b = values[i - 1], values[i]
        if a is None or b is None:
            continue
        if a <= upper < b:
            out[i] = 1
        elif a >= lower > b:
            out[i] = -1
    return out


def signals_for_method(method, variant, bars):
    family, length_text, mode = variant.split("_")
    if family != method:
        raise ValueError(f"variant {variant} does not match {method}")
    length = int(length_text)
    high = [float(b["high"]) for b in bars]
    low = [float(b["low"]) for b in bars]
    close = [float(b["close"]) for b in bars]
    volume = [float(b.get("volume", 0)) for b in bars]
    n = len(bars)
    entries = [0] * n

    if method == "aroon":
        hi = _rolling_extreme(high, length + 1, True)
        lo = _rolling_extreme(low, length + 1, False)
        prior = 0
        for i in range(length, n):
            up = 100 * (length - (i - hi[i][1])) / length
            down = 100 * (length - (i - lo[i][1])) / length
            side = 1 if up > down else -1 if down > up else 0
            if side != prior and side and (mode == "cross" or (up >= 70 and down <= 30 if side > 0 else down >= 70 and up <= 30)):
                entries[i] = side
            prior = side

    elif method == "williams":
        hi = _rolling_extreme(high, length, True)
        lo = _rolling_extreme(low, length, False)
        values = [None] * n
        for i in range(length - 1, n):
            span = hi[i][0] - lo[i][0]
            values[i] = -100 * (hi[i][0] - close[i]) / span if span else -50
        entries = _cross(values, -80 if mode == "rebound" else -20,
                          -20 if mode == "rebound" else -80)

    elif method == "stoch":
        hi = _rolling_extreme(high, length, True)
        lo = _rolling_extreme(low, length, False)
        raw = [50.0] * n
        for i in range(length - 1, n):
            span = hi[i][0] - lo[i][0]
            raw[i] = 100 * (close[i] - lo[i][0]) / span if span else 50
        k = _sma(raw, 3)
        d = _sma([v if v is not None else 50 for v in k], 3)
        for i in range(max(length + 4, 2), n):
            if k[i - 1] <= d[i - 1] and k[i] > d[i] and (mode == "cross" or k[i] < 30):
                entries[i] = 1
            elif k[i - 1] >= d[i - 1] and k[i] < d[i] and (mode == "cross" or k[i] > 70):
                entries[i] = -1

    elif method == "keltner":
        middle = _ema(close, length)
        tr = [high[0] - low[0]] + [max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])) for i in range(1, n)]
        atr = _rma(tr, length)
        multiple = 1.5 if mode == "narrow" else 2.0
        for i in range(length, n):
            if middle[i - 1] is None or atr[i - 1] is None:
                continue
            if close[i] > middle[i] + multiple * atr[i] and close[i - 1] <= middle[i - 1] + multiple * atr[i - 1]:
                entries[i] = 1
            elif close[i] < middle[i] - multiple * atr[i] and close[i - 1] >= middle[i - 1] - multiple * atr[i - 1]:
                entries[i] = -1

    elif method == "ichimoku":
        conversion = 9 if length == 26 else 7
        span_b_length = 52 if length == 26 else 44
        hi_conv = _rolling_extreme(high, conversion, True)
        lo_conv = _rolling_extreme(low, conversion, False)
        hi_base = _rolling_extreme(high, length, True)
        lo_base = _rolling_extreme(low, length, False)
        hi_span = _rolling_extreme(high, span_b_length, True)
        lo_span = _rolling_extreme(low, span_b_length, False)
        a, b = [None] * n, [None] * n
        for i in range(span_b_length - 1, n):
            conv = (hi_conv[i][0] + lo_conv[i][0]) / 2
            base = (hi_base[i][0] + lo_base[i][0]) / 2
            a[i] = (conv + base) / 2
            b[i] = (hi_span[i][0] + lo_span[i][0]) / 2
        for i in range(span_b_length + length, n):
            # A value plotted at i was computed at i-length; never use the
            # future projection at the calculation bar.
            now_hi, now_lo = max(a[i-length], b[i-length]), min(a[i-length], b[i-length])
            old_hi, old_lo = max(a[i-length-1], b[i-length-1]), min(a[i-length-1], b[i-length-1])
            bullish = close[i] > now_hi and close[i - 1] <= old_hi
            bearish = close[i] < now_lo and close[i - 1] >= old_lo
            if mode == "aligned":
                bullish &= a[i-length] > b[i-length]
                bearish &= a[i-length] < b[i-length]
            entries[i] = 1 if bullish else -1 if bearish else 0

    elif method == "mfi":
        typical = [(high[i] + low[i] + close[i]) / 3 for i in range(n)]
        pos, neg = [0.0] * n, [0.0] * n
        for i in range(1, n):
            flow = typical[i] * volume[i]
            if typical[i] > typical[i-1]:
                pos[i] = flow
            elif typical[i] < typical[i-1]:
                neg[i] = flow
        p_sum, n_sum = _sma(pos, length), _sma(neg, length)
        values = [None if p_sum[i] is None else 100 * p_sum[i] / (p_sum[i] + n_sum[i]) if p_sum[i] + n_sum[i] else 50 for i in range(n)]
        entries = _cross(values, 20 if mode == "rebound" else 80, 80 if mode == "rebound" else 20)

    elif method == "cmf":
        flow = [((2 * close[i] - high[i] - low[i]) / (high[i] - low[i]) if high[i] > low[i] else 0) * volume[i] for i in range(n)]
        f_sum, v_sum = _sma(flow, length), _sma(volume, length)
        values = [None if f_sum[i] is None else f_sum[i] / v_sum[i] if v_sum[i] else 0 for i in range(n)]
        threshold = 0 if mode == "zero" else 0.05
        entries = _cross(values, threshold, -threshold)

    elif method == "dmi":
        tr = [high[0] - low[0]]
        pdm, ndm = [0.0], [0.0]
        for i in range(1, n):
            tr.append(max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1])))
            up, down = high[i] - high[i-1], low[i-1] - low[i]
            pdm.append(up if up > down and up > 0 else 0)
            ndm.append(down if down > up and down > 0 else 0)
        atr, rp, rn = _rma(tr, length), _rma(pdm, length), _rma(ndm, length)
        plus = [0 if atr[i] is None or not atr[i] else 100 * rp[i] / atr[i] for i in range(n)]
        minus = [0 if atr[i] is None or not atr[i] else 100 * rn[i] / atr[i] for i in range(n)]
        dx = [100 * abs(plus[i] - minus[i]) / (plus[i] + minus[i]) if plus[i] + minus[i] else 0 for i in range(n)]
        adx = _rma(dx, length)
        threshold = 20 if mode == "adx20" else 25
        for i in range(2 * length, n):
            if adx[i] >= threshold:
                if plus[i] > minus[i] and plus[i-1] <= minus[i-1]:
                    entries[i] = 1
                elif minus[i] > plus[i] and minus[i-1] <= plus[i-1]:
                    entries[i] = -1

    elif method == "cci":
        typical = [(high[i] + low[i] + close[i]) / 3 for i in range(n)]
        average = _sma(typical, length)
        values = [None] * n
        for i in range(length - 1, n):
            deviation = sum(abs(typical[j] - average[i]) for j in range(i - length + 1, i + 1)) / length
            values[i] = (typical[i] - average[i]) / (0.015 * deviation) if deviation else 0
        entries = _cross(values, -100 if mode == "rebound" else 100,
                          100 if mode == "rebound" else -100)
    else:
        raise ValueError(f"unknown family: {method}")
    return entries, [0] * n
