"""Return over trailing full calendar months from a continuous equity curve."""

from __future__ import annotations


def trailing_period(months: list[dict], length: int) -> dict | None:
    ordered = sorted(months, key=lambda row: row["start"])
    tail = ordered[-length:]
    if len(tail) != length:
        return None
    indices = [int(row["start"][:4]) * 12 + int(row["start"][5:7]) for row in tail]
    if any(right - left != 1 for left, right in zip(indices, indices[1:])):
        return None
    start = float(tail[0]["starting_equity_rub"])
    end = float(tail[-1]["ending_equity_rub"])
    if start <= 0:
        return None
    return {"return_pct": round(100 * (end / start - 1), 2),
            "pnl_rub": round(end - start, 2),
            "from_month": tail[0]["start"][:7],
            "through_month": tail[-1]["start"][:7]}
