"""Fixed ichimoku experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'ichimoku-22-break-1d'
TIMEFRAME = '1D'
VARIANT = 'ichimoku_22_break'
PAPER_SYMBOLS = ['VKCO', 'VTBR', 'SMLT', 'HYDR', 'MAGN', 'MSNG', 'UNAC', 'UGLD']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('ichimoku', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
