"""Fixed stoch experiment rule; frozen source signals are reused."""
from src.research.classic_indicator_grid import signals_for_method
STRATEGY_ID = 'stoch-28-cross-1w'
TIMEFRAME = '1W'
VARIANT = 'stoch_28_cross'
PAPER_SYMBOLS = ['VKCO', 'BELU', 'RNFT', 'RUAL', 'SMLT', 'SFIN', 'FEES', 'HYDR', 'IRAO']
def signal(bars):
    if not bars:
        return None
    entries, _ = signals_for_method('stoch', VARIANT, bars)
    return "long" if entries[-1] > 0 else "short" if entries[-1] < 0 else None
