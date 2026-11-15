"""Fixed aroon experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'aroon-25-cross-1d'
TIMEFRAME = '1D'
VARIANT = 'aroon_25_cross'
PAPER_SYMBOLS = ['VKCO', 'SMLT', 'MSNG', 'HYDR', 'VTBR', 'PLZL', 'UGLD', 'ASTR', 'UNAC']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('aroon', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
