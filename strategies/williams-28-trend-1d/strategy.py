"""Fixed williams experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'williams-28-trend-1d'
TIMEFRAME = '1D'
VARIANT = 'williams_28_trend'
PAPER_SYMBOLS = ['VKCO', 'POSI', 'SMLT', 'HYDR', 'MAGN', 'ALRS', 'SELG', 'PLZL', 'UNAC', 'UGLD']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('williams', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
