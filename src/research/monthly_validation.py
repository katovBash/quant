"""Check complete-month rows before reporting historical returns."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date


def validate_monthly_rows(rows: list[dict]) -> dict:
    """Validate dates, equity arithmetic and trade counts; expose calendar gaps."""
    required = {"symbol", "timeframe", "variant", "start", "end_exclusive",
                "starting_equity_rub", "ending_equity_rub", "return_pct", "pnl_rub",
                "closed_trades", "winning_trades"}
    if not rows or not required <= set(rows[0]):
        raise ValueError(f"monthly rows need {sorted(required)}")
    counts = {"duplicate_month_rows": 0, "invalid_calendar_rows": 0,
              "invalid_equity_rows": 0, "return_mismatch_rows": 0,
              "pnl_mismatch_rows": 0, "invalid_trade_rows": 0}
    seen = set()
    by_pair: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    examples = []

    def flag(kind: str, row: dict) -> None:
        counts[kind] += 1
        if len(examples) < 10:
            examples.append({"issue": kind, "symbol": row.get("symbol"),
                             "timeframe": row.get("timeframe"),
                             "variant": row.get("variant"), "month": row.get("start", "")[:7]})

    for row in rows:
        key = (row["symbol"], row["timeframe"], row["variant"])
        try:
            start = date.fromisoformat(row["start"])
            end = date.fromisoformat(row["end_exclusive"])
            expected_end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
            if start.day != 1 or end != expected_end:
                raise ValueError("not one full calendar month")
            month_index = start.year * 12 + start.month
        except (ValueError, TypeError):
            flag("invalid_calendar_rows", row)
            continue
        if (key, month_index) in seen:
            flag("duplicate_month_rows", row)
        seen.add((key, month_index))
        by_pair[key].add(month_index)
        try:
            starting = float(row["starting_equity_rub"])
            ending = float(row["ending_equity_rub"])
            reported_return = float(row["return_pct"])
            reported_pnl = float(row["pnl_rub"])
            if not all(math.isfinite(value) for value in (starting, ending, reported_return, reported_pnl)) or starting <= 0:
                raise ValueError("invalid equity")
        except (ValueError, TypeError):
            flag("invalid_equity_rows", row)
            continue
        if abs(reported_pnl - (ending - starting)) > 0.02:
            flag("pnl_mismatch_rows", row)
        if abs(reported_return - 100 * (ending / starting - 1)) > 0.0002:
            flag("return_mismatch_rows", row)
        try:
            closed = int(row["closed_trades"])
            winning = int(row["winning_trades"])
            if closed < 0 or winning < 0 or winning > closed:
                raise ValueError("invalid trades")
        except (ValueError, TypeError):
            flag("invalid_trade_rows", row)

    gap_pairs = missing_months = 0
    gap_examples = []
    missing_by_symbol_frame: dict[tuple[str, str], set[int]] = defaultdict(set)
    example_frames = set()
    for key, indices in by_pair.items():
        ordered = sorted(indices)
        missing = {index for left, right in zip(ordered, ordered[1:])
                   for index in range(left + 1, right)}
        if missing:
            gap_pairs += 1
            missing_months += len(missing)
            frame = key[:2]
            missing_by_symbol_frame[frame].update(missing)
            if frame not in example_frames and len(gap_examples) < 10:
                example_frames.add(frame)
                labels = [f"{(index - 1) // 12:04d}-{(index - 1) % 12 + 1:02d}"
                          for index in sorted(missing)[:6]]
                gap_examples.append({"symbol": key[0], "timeframe": key[1],
                                     "example_variant": key[2], "missing_months": len(missing),
                                     "first_missing": labels})
    return {"rows": len(rows), "pairs": len(by_pair), **counts,
            "gap_pairs": gap_pairs, "missing_months_inside_history": missing_months,
            "affected_symbol_timeframes": len(missing_by_symbol_frame),
            "unique_missing_symbol_months": sum(len(value) for value in missing_by_symbol_frame.values()),
            "invalid_examples": examples, "gap_examples": gap_examples,
            "ok": not any(counts.values()), "continuous": gap_pairs == 0}
