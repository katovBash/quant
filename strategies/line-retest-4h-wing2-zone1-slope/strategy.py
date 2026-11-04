"""Frozen 4H confirmed-line retest; selected MGNT review pair."""

from src.research.selected_line_retest import decision, events

STRATEGY_ID = "line-retest-4h-wing2-zone1-slope"
TIMEFRAME = "4H"
PAPER_SYMBOLS = ["MGNT"]
REQUIRES_HOURLY = True
WING = 2
ZONE_ATR = 1.0


def event_series(bars, hourly_bars):
    return events(bars, hourly_bars, wing=WING, zone_atr=ZONE_ATR)


def signal(bars, *, hourly_bars, position=0):
    return decision(bars, hourly_bars, position, wing=WING, zone_atr=ZONE_ATR)
