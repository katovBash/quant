"""Fixed cci experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'cci-20-trend-1d'
TIMEFRAME = '1D'
VARIANT = 'cci_20_trend'
PAPER_SYMBOLS = ['SMLT', 'MSNG', 'VTBR', 'PLZL', 'SIBN', 'ASTR', 'UNAC', 'TATN', 'TATNP', 'UGLD']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('cci', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
