"""Calendar-year performance from complete monthly account snapshots."""

from collections import defaultdict


def calendar_years(months: list[dict]) -> list[dict]:
    """Return each calendar year's PnL; label years with fewer than 12 months YTD."""
    grouped = defaultdict(list)
    for month in months:
        grouped[month["start"][:4]].append(month)
    result = []
    for year, items in sorted(grouped.items()):
        ordered = sorted(items, key=lambda row: row["start"])
        first = int(ordered[0]["start"][5:7])
        last = int(ordered[-1]["start"][5:7])
        start_equity = float(ordered[0]["starting_equity_rub"])
        end_equity = float(ordered[-1]["ending_equity_rub"])
        complete = len(ordered) == 12 and first == 1 and last == 12
        result.append({"year": year, "months": len(ordered), "first_month": first,
                       "last_month": last, "complete": complete,
                       "pnl_rub": round(end_equity - start_equity, 2),
                       "return_pct": round(100 * (end_equity / start_equity - 1), 2)
                       if start_equity > 0 else None})
    return result
