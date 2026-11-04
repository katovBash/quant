"""Frozen 4H confirmed-line retest; selected IRKT and WUSH review pairs."""

from src.research.selected_line_retest import decision, events

STRATEGY_ID = "line-retest-4h-wing1-zone05-slope"
TIMEFRAME = "4H"
PAPER_SYMBOLS = ["IRKT", "WUSH"]
REQUIRES_HOURLY = True
WING = 1
ZONE_ATR = 0.5


def event_series(bars, hourly_bars):
    return events(bars, hourly_bars, wing=WING, zone_atr=ZONE_ATR)


def signal(bars, *, hourly_bars, position=0):
    return decision(bars, hourly_bars, position, wing=WING, zone_atr=ZONE_ATR)
