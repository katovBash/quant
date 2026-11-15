"""Fixed cmf experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'cmf-20-buffer-1d'
TIMEFRAME = '1D'
VARIANT = 'cmf_20_buffer'
PAPER_SYMBOLS = ['UNAC', 'ASTR', 'SGZH']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('cmf', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
